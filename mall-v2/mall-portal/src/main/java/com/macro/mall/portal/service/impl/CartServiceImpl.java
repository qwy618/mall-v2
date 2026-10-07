package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.CartItemMapper;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.CartItem;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.mbg.model.Sku;
import com.macro.mall.portal.dao.CartMergeParam;
import com.macro.mall.portal.service.CartService;
import com.macro.mall.portal.vo.CartItemVO;
import com.macro.mall.service.SkuStockService;
import org.redisson.api.RBucket;
import org.redisson.api.RMap;
import org.redisson.api.RedissonClient;
import org.redisson.client.codec.StringCodec;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class CartServiceImpl implements CartService {

    private final CartItemMapper cartItemMapper;
    private final SkuMapper skuMapper;
    private final ProductMapper productMapper;
    private final RedissonClient redisson;
    private final ObjectMapper objectMapper;
    private final SkuStockService skuStockService;

    public CartServiceImpl(CartItemMapper cartItemMapper,
                           SkuMapper skuMapper,
                           ProductMapper productMapper,
                           RedissonClient redisson,
                           ObjectMapper objectMapper,
                           SkuStockService skuStockService) {
        this.cartItemMapper = cartItemMapper;
        this.skuMapper = skuMapper;
        this.productMapper = productMapper;
        this.redisson = redisson;
        this.objectMapper = objectMapper;
        this.skuStockService = skuStockService;
    }

    // ===== 购物车 Redis 缓存（债务17）：Hash 存原始行 + 写后失效 + 空值防穿透 =====
    // 数据 key = cart:items:{memberId}  (Hash, field=skuId, value=CartItem JSON)
    // 标记 key = cart:cached:{memberId} (String, 存在即表示"该会员车已被缓存过，含空车")
    //   —— 用于区分"缓存未命中"与"已缓存但空车"，避免空车每次都打 DB（防穿透）
    // 只缓存 cart_item 原始行；在线判定(sku/product 实时价、下架)仍每次查，保证价格/状态不陈旧
    private static final String KEY_PREFIX = "cart:items:";
    private static final String CACHED_PREFIX = "cart:cached:";
    private static final long CART_TTL_SECONDS = 1800L; // 30min 兜底，写后失效为主

    @Override
    public CommonResult<Void> add(Long memberId, Long skuId, Integer quantity) {
        if (quantity == null || quantity < 1) {
            return CommonResult.validateFailed("购买数量必须大于0");
        }
        Sku sku = skuMapper.selectById(skuId);
        if (sku == null) {
            return CommonResult.failed("商品不存在");
        }
        LambdaQueryWrapper<CartItem> qw = new LambdaQueryWrapper<>();
        qw.eq(CartItem::getMemberId, memberId).eq(CartItem::getSkuId, skuId);
        CartItem exist = cartItemMapper.selectOne(qw);
        if (exist != null) {
            // 同会员同 sku 已存在：数量累加（依赖 uk_member_sku 唯一索引保证只有一行）
            exist.setQuantity(exist.getQuantity() + quantity);
            cartItemMapper.updateById(exist);
        } else {
            cartItemMapper.insert(buildSnapshotItem(memberId, sku, quantity));
        }
        invalidate(memberId);
        return CommonResult.success(null);
    }

    @Override
    public CommonResult<Void> updateQuantity(Long memberId, Long cartItemId, Integer quantity) {
        if (quantity == null || quantity < 1) {
            return CommonResult.validateFailed("购买数量必须大于0");
        }
        CartItem item = cartItemMapper.selectById(cartItemId);
        if (item == null) {
            return CommonResult.failed("购物车项不存在");
        }
        if (!item.getMemberId().equals(memberId)) {   // ★ 防篡改删/改别人的车
            return CommonResult.failed("无权操作");
        }
        item.setQuantity(quantity);
        cartItemMapper.updateById(item);
        invalidate(memberId);
        return CommonResult.success(null);
    }

    @Override
    public CommonResult<Void> delete(Long memberId, Long cartItemId) {
        CartItem item = cartItemMapper.selectById(cartItemId);
        if (item == null) {
            return CommonResult.failed("购物车项不存在");
        }
        if (!item.getMemberId().equals(memberId)) {   // ★ 同上
            return CommonResult.failed("无权操作");
        }
        cartItemMapper.deleteById(cartItemId);
        invalidate(memberId);
        return CommonResult.success(null);
    }

    @Override
    public CommonResult<Void> check(Long memberId, Long cartItemId, Integer checked) {
        if (checked == null || (checked != 0 && checked != 1)) {
            return CommonResult.validateFailed("checked 只能是0或1");
        }
        CartItem item = cartItemMapper.selectById(cartItemId);
        if (item == null) {
            return CommonResult.failed("购物车项不存在");
        }
        if (!item.getMemberId().equals(memberId)) {   // ★ 同上
            return CommonResult.failed("无权操作");
        }
        item.setChecked(checked);
        cartItemMapper.updateById(item);
        invalidate(memberId);
        return CommonResult.success(null);
    }

    @Override
    public CommonResult<List<CartItemVO>> list(Long memberId) {
        // 走缓存：命中(含空车)直接返回原始行，未命中查 DB 并回填
        List<CartItem> items = loadCartItems(memberId);
        if (items.isEmpty()) {
            return CommonResult.success(new ArrayList<>());
        }
        Set<Long> skuIds = items.stream().map(CartItem::getSkuId).collect(Collectors.toSet());
        List<Sku> skus = skuMapper.selectBatchIds(skuIds);
        Map<Long, Sku> skuMap = skus.stream()
                .collect(Collectors.toMap(Sku::getId, Function.identity()));
        Set<Long> productIds = skus.stream().map(Sku::getProductId).collect(Collectors.toSet());
        Map<Long, Product> productMap = productMapper.selectBatchIds(productIds).stream()
                .collect(Collectors.toMap(Product::getId, Function.identity()));

        List<CartItemVO> vos = new ArrayList<>();
        for (CartItem it : items) {
            Sku sku = skuMap.get(it.getSkuId());
            Product p = sku != null ? productMap.get(sku.getProductId()) : null;
            // 在线判定：SKU 与商品都存在，且商品 status=1（上架）。product 物理删除 → p==null → 失效
            boolean online = sku != null && p != null && Integer.valueOf(1).equals(p.getStatus());
            CartItemVO vo = new CartItemVO();
            vo.setCartItemId(it.getId());
            vo.setSkuId(it.getSkuId());
            vo.setProductId(it.getProductId());
            vo.setSkuCode(sku != null ? sku.getSkuCode() : it.getSkuCode());
            vo.setProductName(p != null ? p.getName() : it.getProductName());
            vo.setPic(resolvePic(sku, p, it.getPic()));
            vo.setSpData(it.getSpData());
            vo.setPrice(online ? sku.getPrice() : it.getPrice());
            // 债务5：展示**可售**库存（stock − lock_stock），不是实物库存 ——
            // 否则已被别人待支付订单占住的量会显示成"还有货"，点进去下单才发现没库存
            vo.setStock(online ? skuStockService.available(sku) : 0);
            vo.setQuantity(it.getQuantity());
            vo.setChecked(it.getChecked());
            vo.setOffline(!online);
            vos.add(vo);
        }
        return CommonResult.success(vos);
    }

    @Override
    public CommonResult<Void> merge(Long memberId, List<CartMergeParam> items) {
        if (items == null || items.isEmpty()) {
            return CommonResult.success(null);
        }
        for (CartMergeParam it : items) {
            if (it.getSkuId() == null) continue;
            int qty = it.getQuantity() == null ? 1 : it.getQuantity();
            if (qty < 1) qty = 1;
            Sku sku = skuMapper.selectById(it.getSkuId());
            if (sku == null) continue;   // 跳过已失效的暂存项，不报错
            LambdaQueryWrapper<CartItem> qw = new LambdaQueryWrapper<>();
            qw.eq(CartItem::getMemberId, memberId).eq(CartItem::getSkuId, sku.getId());
            CartItem exist = cartItemMapper.selectOne(qw);
            if (exist != null) {
                exist.setQuantity(exist.getQuantity() + qty);
                cartItemMapper.updateById(exist);
            } else {
                cartItemMapper.insert(buildSnapshotItem(memberId, sku, qty));
            }
        }
        invalidate(memberId);
        return CommonResult.success(null);
    }

    @Override
    public void evictCartCache(Long memberId) {
        // 暴露给绕过本 Service 的写路径（下单清车直接物理删行）在事务提交后调用，
        // 否则下次读命中旧缓存会出现"已下单商品仍在购物车"的幽灵条目
        invalidate(memberId);
    }

    /** 读购物车原始行：缓存命中(含空车)直接返回；未命中查 DB 并回填（空车也打标记，防穿透） */
    private List<CartItem> loadCartItems(Long memberId) {
        RBucket<String> flag = redisson.getBucket(CACHED_PREFIX + memberId, StringCodec.INSTANCE);
        if (flag.isExists()) {
            // 命中：从 Hash 取全部 CartItem JSON 反序列化
            RMap<String, String> map = redisson.getMap(KEY_PREFIX + memberId, StringCodec.INSTANCE);
            Collection<String> vals = map.readAllValues();
            List<CartItem> items = new ArrayList<>(vals.size());
            for (String v : vals) {
                items.add(fromJson(v));
            }
            return items;
        }
        // 未命中：查 DB 行（不含在线判定，那步仍每次做）
        LambdaQueryWrapper<CartItem> qw = new LambdaQueryWrapper<>();
        qw.eq(CartItem::getMemberId, memberId);
        List<CartItem> items = cartItemMapper.selectList(qw);
        long ttl = ttlSeconds();
        RMap<String, String> map = redisson.getMap(KEY_PREFIX + memberId, StringCodec.INSTANCE);
        if (!items.isEmpty()) {
            Map<String, String> m = new HashMap<>(items.size());
            for (CartItem it : items) {
                m.put(String.valueOf(it.getSkuId()), toJson(it));
            }
            map.putAll(m);
            map.expire(ttl, TimeUnit.SECONDS);
        }
        // 即使空车也打标记，避免缓存穿透（每次都打 DB）
        flag.set("1", ttl, TimeUnit.SECONDS);
        return items;
    }

    /** 写后失效：删除 Hash + 标记，下次读重建（保证 cart_item 与缓存一致） */
    private void invalidate(Long memberId) {
        redisson.getMap(KEY_PREFIX + memberId, StringCodec.INSTANCE).clear();
        redisson.getBucket(CACHED_PREFIX + memberId, StringCodec.INSTANCE).delete();
    }

    /** TTL 加 0~300s 随机抖动，避免大量购物车 key 同时过期造成缓存雪崩 */
    private long ttlSeconds() {
        return CART_TTL_SECONDS + (long) (Math.random() * 300);
    }

    private String toJson(CartItem item) {
        try {
            return objectMapper.writeValueAsString(item);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("购物车缓存序列化失败", e);
        }
    }

    private CartItem fromJson(String json) {
        try {
            return objectMapper.readValue(json, CartItem.class);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("购物车缓存反序列化失败", e);
        }
    }

    /** 构造一条带商品快照的购物车项（债务16-快照：加入时落 name/pic/spData/price） */
    private CartItem buildSnapshotItem(Long memberId, Sku sku, Integer quantity) {
        CartItem item = new CartItem();
        item.setMemberId(memberId);
        item.setSkuId(sku.getId());
        item.setQuantity(quantity);
        item.setChecked(1);
        Product p = productMapper.selectById(sku.getProductId());
        item.setProductId(sku.getProductId());
        item.setProductName(p != null ? p.getName() : null);
        item.setSkuCode(sku.getSkuCode());
        item.setPic(resolvePic(sku, p, null));
        item.setSpData(sku.getSpData());
        item.setPrice(sku.getPrice());
        return item;
    }

    /**
     * 取购物车展示图：优先 SKU 图，SKU 无图（空串/NULL）时回退 SPU 商品图，最后回退兜底值（如快照）。
     * 本项目 SKU 表多数无独立图片，商品图存在 product.pic，故必须回退，否则合并/加购后图会丢失。
     */
    private String resolvePic(Sku sku, Product p, String fallback) {
        if (sku != null && StringUtils.hasText(sku.getPic())) {
            return sku.getPic();
        }
        if (p != null && StringUtils.hasText(p.getPic())) {
            return p.getPic();
        }
        return fallback;
    }
}
