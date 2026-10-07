package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.ResultCode;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.*;
import com.macro.mall.mbg.model.*;
import com.macro.mall.portal.config.MqConstants;
import com.macro.mall.portal.dao.CreateOrderParam;
import com.macro.mall.portal.dao.OrderItemParam;
import com.macro.mall.portal.dao.OrderPreviewParam;
import com.macro.mall.portal.service.CartService;
import com.macro.mall.portal.service.OrderIdempotentService;
import com.macro.mall.portal.service.OrderService;
import com.macro.mall.portal.vo.OrderDetailVO;
import com.macro.mall.portal.vo.OrderPreviewVO;
import com.macro.mall.service.MemberLevelService;
import com.macro.mall.service.MemberPointsService;
import com.macro.mall.service.SkuStockService;
import lombok.extern.slf4j.Slf4j;
import org.redisson.api.RAtomicLong;
import org.redisson.api.RedissonClient;
import org.redisson.client.codec.StringCodec;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

import com.fasterxml.jackson.databind.ObjectMapper;

@Service
@Slf4j
public class OrderServiceImpl implements OrderService {

    @Autowired private OrderMapper orderMapper;
    @Autowired private OrderItemMapper orderItemMapper;
    @Autowired private SkuMapper skuMapper;
    @Autowired private ProductMapper productMapper;
    @Autowired private MemberAddressMapper memberAddressMapper;
    @Autowired private CartItemMapper cartItemMapper;
    @Autowired private CartService cartService;
    @Autowired private RedissonClient redisson;
    @Autowired private RabbitTemplate rabbitTemplate;
    @Autowired private CouponMapper couponMapper;
    @Autowired private CouponHistoryMapper couponHistoryMapper;
    @Autowired private PaymentMapper paymentMapper;
    @Autowired private OrderOperateHistoryMapper historyMapper;
    @Autowired private OrderIdempotentService orderIdempotentService;
    @Autowired private MemberMapper memberMapper;
    @Autowired private MemberLevelService memberLevelService;
    @Autowired private MemberPointsService memberPointsService;
    @Autowired private SkuStockService skuStockService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> createOrder(Long memberId, CreateOrderParam param) {
        // 0. 下单幂等（债务23）：Redis 一次性 Token 原子认领，杜绝双击/重试重复下单
        String token = param.getSubmitToken();
        if (token == null || token.isBlank()) {
            return CommonResult.failed("缺少幂等令牌，请刷新页面重试");
        }
        Long claimResult = orderIdempotentService.claim(memberId, token);
        if (claimResult == null) return CommonResult.failed("系统繁忙，请稍后重试");
        if (claimResult == -1L) return CommonResult.failed("令牌无效或已过期，请刷新页面重试");
        if (claimResult == -2L) return CommonResult.failed("订单提交处理中，请勿重复提交");
        if (claimResult > 0L) return CommonResult.success(claimResult);   // 幂等：返回同一笔单

        // settled=true 表示已确定结束（下单成功 or 回查命中），finally 不再回退令牌
        boolean settled = false;
        try {
            // 0.1 兜底：Redis 映射丢失时按 token 回查已建订单（无副作用，放在扣库存之前）
            Order existed = orderMapper.selectOne(new LambdaQueryWrapper<Order>()
                    .eq(Order::getSubmitToken, token).last("limit 1"));
            if (existed != null) {
                orderIdempotentService.finish(memberId, token, existed.getId());
                settled = true;
                return CommonResult.success(existed.getId());
            }

            CommonResult<Long> res = doCreateOrder(memberId, param, token);
            settled = res != null && ResultCode.SUCCESS.equals(res.getCode()) && res.getData() != null;
            return res;
        } finally {
            // 业务失败 / 异常：回退令牌，允许用户修正后重试（成功路径 settled=true 不回退）
            if (!settled) {
                try {
                    orderIdempotentService.release(memberId, token);
                } catch (Exception e) {
                    log.error("幂等令牌回退失败 memberId={} token={}", memberId, token, e);
                }
            }
        }
    }

    /**
     * 下单主体逻辑（事务由 {@link #createOrder} 开启，本方法在同事务内执行）。
     * 拆出以便外层统一处理幂等令牌的 成功标记 / 失败回退。
     */
    private CommonResult<Long> doCreateOrder(Long memberId, CreateOrderParam param, String token) {
        // 1. 地址归属校验（防越权）
        MemberAddress addr = memberAddressMapper.selectById(param.getAddressId());
        if (addr == null || !memberId.equals(addr.getMemberId())) {
            return CommonResult.failed("地址不存在");
        }

        // 2. 若用券，先取券模板（校验存在 + 使用时间 + 拿到 useType/categoryId/productId）
        Coupon coupon = null;
        if (param.getCouponId() != null) {
            coupon = couponMapper.selectById(param.getCouponId());
            if (coupon == null) throw new BusinessException("优惠券不存在");
            LocalDateTime now = LocalDateTime.now();
            if (coupon.getStartTime() != null && now.isBefore(coupon.getStartTime()))
                throw new BusinessException("优惠券未到使用时间");
            if (coupon.getEndTime() != null && now.isAfter(coupon.getEndTime()))
                throw new BusinessException("优惠券已过期");
        }

        // 3. 订单号（Redisson 原子自增，按日）
        String orderSn = getOrderSn();

        // 4. 解析行项目（**只读**：查 SKU/商品、校验购物车归属、算行小计与券适用范围）
        //    注意：本步骤不再动库存，锁定库存单独抽到 lockStock（见第 6 步），
        //    以便 preview 复用「解析 + 算钱」而跳过「扣库存」。
        List<ResolvedItem> rows = resolveItems(memberId, param.getItems(), coupon);
        // 4.1 收集结算后要清理的购物车条目
        List<Long> toDeleteCartIds = new ArrayList<>();
        for (ResolvedItem r : rows) {
            if (r.cartItemId != null) toDeleteCartIds.add(r.cartItemId);
        }

        // 5. 三类优惠插入前一次算定：会员折扣(promotion) → 优惠券(coupon) → 积分抵扣(integration)
        //    computeAmounts 是**全站唯一的金额计算口径**，preview 与 create 共用同一段代码。
        Member member = memberMapper.selectById(memberId);
        if (member == null) throw new BusinessException("会员不存在");
        Amounts amounts = computeAmounts(member, rows, coupon, param.getUseIntegration());

        // 6. 原子**锁定**库存（唯一"有副作用"的一步，仅 create 调用）：只预占，不动实物库存
        lockStock(rows);

        // 7. 构建订单项（取图口径：优先 SKU 图，SKU 无图回退 SPU 商品图）
        List<OrderItem> items = buildOrderItems(orderSn, rows);

        // 8. 建订单（金额一次性写全，避免"先插后改"）
        Order order = new Order();
        order.setOrderSn(orderSn);
        order.setMemberId(memberId);
        order.setAddressId(param.getAddressId());
        order.setTotalAmount(amounts.total);
        order.setFreightAmount(BigDecimal.ZERO);
        order.setCouponId(coupon == null ? null : coupon.getId());
        order.setCouponAmount(amounts.couponAmount);
        order.setPromotionAmount(amounts.promotionAmount);
        order.setUseIntegration(amounts.useIntegration);
        order.setIntegrationAmount(amounts.integrationAmount);
        order.setPayAmount(amounts.payAmount);
        order.setStatus(0);
        order.setDeleteStatus(0);
        order.setReceiverName(addr.getReceiverName());
        order.setReceiverPhone(addr.getPhone());
        order.setReceiverProvince(addr.getProvince());
        order.setReceiverCity(addr.getCity());
        order.setReceiverDistrict(addr.getDistrict());
        order.setReceiverDetailAddress(addr.getDetailAddress());
        order.setSubmitToken(token);   // 幂等令牌落库，uk_submit_token 作第二道防线（债务23）
        orderMapper.insert(order);
        Long orderId = order.getId();
        recordHistory(orderId, order.getOrderSn(), "会员" + memberId, "CREATE", "提交订单");

        // 9. 优惠券核销（乐观条件更新防并发，回填 orderId；失败抛异常整单回滚）
        if (coupon != null) {
            int n = couponHistoryMapper.useCoupon(memberId, coupon.getId().longValue(), orderId);
            if (n == 0) throw new BusinessException("优惠券不可用或已被使用");
        }

        // 9.1 积分扣减 + 流水（债务18）：条件更新防并发超用，失败抛异常整单回滚
        if (amounts.useIntegration > 0) {
            memberPointsService.consumeForOrder(memberId, orderId, orderSn, amounts.useIntegration);
        }

        // 9.2 优惠分摊到订单项（债务7：退款按 real_amount 退，防薅羊毛）
        allocateDiscount(items, amounts.promotionAmount, amounts.couponAmount, amounts.integrationAmount);

        // 10. 插订单项
        items.forEach(oi -> oi.setOrderId(orderId));
        orderItemMapper.insertBatch(items);
        // 11. 清购物车项（物理删）
        if (!toDeleteCartIds.isEmpty()) {
            cartItemMapper.deleteBatchIds(toDeleteCartIds);
        }
        // 12. 事务提交后发送延迟消息
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                // 购物车缓存失效（债务17 修复）：第 11 步直接物理删行绕过了 CartService，
                // 必须在此显式失效，否则 /cart/list 命中旧缓存会出现"已下单商品仍在购物车"的幽灵条目。
                // 放在 afterCommit（而非提交前）是为了让并发读在失效后必定读到已提交的最新行。
                if (!toDeleteCartIds.isEmpty()) {
                    try {
                        cartService.evictCartCache(memberId);
                    } catch (Exception e) {
                        log.error("购物车缓存失效失败 memberId={} orderId={}", memberId, orderId, e);
                    }
                }
                // 幂等令牌回填：事务提交成功后才标记完成，避免"标记完成但事务回滚"（债务23）
                try {
                    orderIdempotentService.finish(memberId, token, orderId);
                } catch (Exception e) {
                    log.error("幂等令牌回填失败 memberId={} token={} orderId={}", memberId, token, orderId, e);
                }
                try {
                    rabbitTemplate.convertAndSend(
                            MqConstants.DELAY_EXCHANGE,
                            MqConstants.DELAY_ROUTING_KEY,
                            String.valueOf(orderId));
                } catch (Exception e) {
                    log.error("订单 {} 延迟取消消息发送失败，需补偿扫描", orderId, e);
                }
            }
        });
        return CommonResult.success(orderId);
    }

    // ==================== 订单试算（债务：金额同源） ====================

    /**
     * 订单试算：**与下单走同一段金额计算代码**，但不产生任何副作用。
     *
     * <p>与 {@link #createOrder} 的差异仅三点：**不扣库存、不落库、不消耗幂等令牌**
     * （也不核销优惠券、不扣积分）。因此本接口天然幂等、可安全地反复调用，
     * 供确认卡片、前端结算页展示「应付金额」。
     *
     * <p>核心保证：确认卡片上的每个数字都来自 {@link #computeAmounts}——
     * 与最终 {@code /order/create} 逐分一致，杜绝金额漂移引发的纠纷。
     */
    @Override
    public CommonResult<OrderPreviewVO> preview(Long memberId, OrderPreviewParam param) {
        if (param.getItems() == null || param.getItems().isEmpty()) {
            return CommonResult.failed("请选择要结算的商品");
        }

        // 1. 地址：显式传入则校验归属；未传则取该会员的默认地址（无地址时为 null，不阻断试算）
        MemberAddress addr = null;
        if (param.getAddressId() != null) {
            addr = memberAddressMapper.selectById(param.getAddressId());
            if (addr == null || !memberId.equals(addr.getMemberId())) {
                return CommonResult.failed("地址不存在");
            }
        } else {
            addr = memberAddressMapper.selectOne(new LambdaQueryWrapper<MemberAddress>()
                    .eq(MemberAddress::getMemberId, memberId)
                    .orderByDesc(MemberAddress::getDefaultStatus)
                    .last("limit 1"));
        }

        // 2. 若用券，先取券模板并校验（与 create 同口径）
        Coupon coupon = null;
        if (param.getCouponId() != null) {
            coupon = couponMapper.selectById(param.getCouponId());
            if (coupon == null) return CommonResult.failed("优惠券不存在");
            LocalDateTime now = LocalDateTime.now();
            if (coupon.getStartTime() != null && now.isBefore(coupon.getStartTime()))
                return CommonResult.failed("优惠券未到使用时间");
            if (coupon.getEndTime() != null && now.isAfter(coupon.getEndTime()))
                return CommonResult.failed("优惠券已过期");
        }

        // 3. 只读解析行项目 + 与 create 同一段金额计算（computeAmounts）
        Member member = memberMapper.selectById(memberId);
        if (member == null) return CommonResult.failed("会员不存在");
        List<ResolvedItem> rows = resolveItems(memberId, param.getItems(), coupon);
        Amounts amounts = computeAmounts(member, rows, coupon, param.getUseIntegration());

        // 4. 组装 VO：每行明细复用与下单相同的分摊算法（allocateDiscount），保证行实付也同源
        List<OrderItem> items = buildOrderItems(null, rows);
        allocateDiscount(items, amounts.promotionAmount, amounts.couponAmount, amounts.integrationAmount);

        OrderPreviewVO vo = new OrderPreviewVO();
        vo.setAddress(addr);
        vo.setTotalAmount(amounts.total);
        vo.setFreightAmount(BigDecimal.ZERO);
        vo.setPromotionAmount(amounts.promotionAmount);
        vo.setCouponAmount(amounts.couponAmount);
        vo.setIntegrationAmount(amounts.integrationAmount);
        vo.setUseIntegration(amounts.useIntegration);
        vo.setPayAmount(amounts.payAmount);
        vo.setLevelName(amounts.levelName);
        vo.setDiscountRate(amounts.discountRate);
        List<OrderPreviewVO.PreviewItem> vos = new ArrayList<>();
        for (OrderItem oi : items) {
            OrderPreviewVO.PreviewItem pi = new OrderPreviewVO.PreviewItem();
            pi.setSkuId(oi.getSkuId());
            pi.setProductId(oi.getProductId());
            pi.setProductName(oi.getProductName());
            pi.setProductPic(oi.getProductPic());
            pi.setSpData(oi.getSpData());
            pi.setPrice(oi.getPrice());
            pi.setQuantity(oi.getQuantity());
            pi.setLineAmount(oi.getPrice().multiply(BigDecimal.valueOf(oi.getQuantity())));
            pi.setPromotionAmount(oi.getPromotionAmount());
            pi.setCouponAmount(oi.getCouponAmount());
            pi.setIntegrationAmount(oi.getIntegrationAmount());
            pi.setRealAmount(oi.getRealAmount());
            vos.add(pi);
        }
        vo.setItems(vos);
        return CommonResult.success(vo);
    }

    // ==================== 抽取的共用方法（preview 与 create 共用，保证口径唯一） ====================

    /** 解析后的行项目：只读快照，供金额计算 / 扣库存 / 建订单项共用。 */
    private static class ResolvedItem {
        Sku sku;
        Product product;
        int quantity;
        Long cartItemId;          // 可空：购物车结算时填
        BigDecimal lineAmount;    // 行原价小计 = price × quantity
        boolean couponApplies;    // 该行是否落在优惠券适用范围内
    }

    /** 三类优惠一次性算定的结果（preview 与 create 共用口径）。 */
    private static class Amounts {
        BigDecimal total = BigDecimal.ZERO;
        BigDecimal promotionAmount = BigDecimal.ZERO;
        BigDecimal couponAmount = BigDecimal.ZERO;
        BigDecimal integrationAmount = BigDecimal.ZERO;
        int useIntegration;
        BigDecimal payAmount = BigDecimal.ZERO;
        String levelName;
        Integer discountRate = 100;
    }

    /**
     * 把下单入参解析成行项目（**全程只读**：查 SKU/商品、校验购物车归属、算行小计与券适用范围）。
     * preview 与 create 共用；**不扣库存、不落库**。
     */
    private List<ResolvedItem> resolveItems(Long memberId, List<OrderItemParam> params, Coupon coupon) {
        List<ResolvedItem> rows = new ArrayList<>();
        for (OrderItemParam ip : params) {
            if (ip.getQuantity() == null || ip.getQuantity() <= 0) {
                throw new BusinessException("数量必须大于0");
            }
            Sku sku = skuMapper.selectById(ip.getSkuId());
            if (sku == null) throw new BusinessException("商品不存在");
            if (ip.getCartItemId() != null) {
                CartItem ci = cartItemMapper.selectById(ip.getCartItemId());
                if (ci == null || !memberId.equals(ci.getMemberId())) {
                    throw new BusinessException("购物车项不存在");
                }
            }
            Product product = productMapper.selectById(sku.getProductId());
            ResolvedItem r = new ResolvedItem();
            r.sku = sku;
            r.product = product;
            r.quantity = ip.getQuantity();
            r.cartItemId = ip.getCartItemId();
            r.lineAmount = sku.getPrice().multiply(BigDecimal.valueOf(ip.getQuantity()));
            r.couponApplies = couponApplies(coupon, product);
            rows.add(r);
        }
        return rows;
    }

    /** 判断某商品是否属于优惠券适用范围（混合商品按券适用小计核算）。 */
    private boolean couponApplies(Coupon coupon, Product product) {
        if (coupon == null) return false;
        Integer useType = coupon.getUseType();
        if (useType == null || useType == 0) return true;                 // 全场通用
        if (useType == 1) {                                               // 指定分类
            return product != null && coupon.getCategoryId() != null
                    && coupon.getCategoryId().equals(product.getCategoryId());
        }
        if (useType == 2) {                                               // 指定商品
            return product != null && coupon.getProductId() != null
                    && coupon.getProductId().equals(product.getId());
        }
        return false;
    }

    /**
     * 三类优惠一次性算定：会员折扣(promotion) → 优惠券(coupon) → 积分抵扣(integration)。
     *
     * <p><b>全站唯一权威口径</b>：preview 与 create 共用本方法，确认卡金额与下单金额必然逐分一致。
     * 口径与原 `doCreateOrder` 第 5 步完全一致，仅挪动位置、未改一行算法。
     */
    private Amounts computeAmounts(Member member, List<ResolvedItem> rows, Coupon coupon,
                                   Integer requestedIntegration) {
        Amounts a = new Amounts();
        BigDecimal total = BigDecimal.ZERO;
        BigDecimal couponBase = BigDecimal.ZERO;   // 券适用商品的小计
        for (ResolvedItem r : rows) {
            total = total.add(r.lineAmount);
            if (r.couponApplies) couponBase = couponBase.add(r.lineAmount);
        }
        a.total = total;

        // 5.1 会员折扣（债务18）：按等级折扣率对商品总额打折
        MemberLevel level = memberLevelService.matchByGrowth(member.getGrowth());
        int discountRate = level == null || level.getDiscountRate() == null ? 100 : level.getDiscountRate();
        a.discountRate = discountRate;
        a.levelName = level == null ? null : level.getName();
        if (discountRate < 100) {
            a.promotionAmount = total.multiply(BigDecimal.valueOf(100 - discountRate))
                    .divide(BigDecimal.valueOf(100), 2, RoundingMode.HALF_UP)
                    .min(total).max(BigDecimal.ZERO);
        }

        // 5.2 优惠券金额：门槛用券适用小计 couponBase，优惠额不超过该小计
        if (coupon != null) {
            BigDecimal min = coupon.getMinPoint() == null ? BigDecimal.ZERO : coupon.getMinPoint();
            if (couponBase.compareTo(min) < 0) {
                throw new BusinessException("该优惠券仅适用于部分商品，当前适用金额未达使用门槛");
            }
            if (coupon.getAmount() == null || coupon.getAmount().compareTo(BigDecimal.ZERO) <= 0) {
                throw new BusinessException("优惠券类型不支持");
            }
            a.couponAmount = coupon.getAmount().min(couponBase).setScale(2, RoundingMode.HALF_UP);
        }

        // 5.3 积分抵扣（债务18）：100 积分 = 1 元，上限 = 券后应付（保证实付不为负）
        BigDecimal beforeIntegration = total.subtract(a.promotionAmount).subtract(a.couponAmount)
                .max(BigDecimal.ZERO);
        if (requestedIntegration != null && requestedIntegration > 0
                && beforeIntegration.compareTo(BigDecimal.ZERO) > 0) {
            int balance = member.getIntegration() == null ? 0 : member.getIntegration();
            // 金额换算上限（向下取整到分），再与申请量、账户余额取最小
            int usableByAmount = beforeIntegration
                    .multiply(BigDecimal.valueOf(MemberPointsService.POINTS_PER_YUAN)).intValue();
            a.useIntegration = Math.min(Math.min(requestedIntegration, balance), usableByAmount);
            if (a.useIntegration > 0) {
                a.integrationAmount = BigDecimal.valueOf(a.useIntegration)
                        .divide(BigDecimal.valueOf(MemberPointsService.POINTS_PER_YUAN), 2, RoundingMode.DOWN);
            }
        }

        // 5.4 实付 = 商品总额 + 运费 − 会员折扣 − 优惠券 − 积分抵扣
        a.payAmount = total.subtract(a.promotionAmount).subtract(a.couponAmount)
                .subtract(a.integrationAmount).setScale(2, RoundingMode.HALF_UP).max(BigDecimal.ZERO);
        // 统一金额精度为 2 位：避免 preview 返回 0 而订单库中是 0.00 的格式差异
        a.total = a.total.setScale(2, RoundingMode.HALF_UP);
        a.promotionAmount = a.promotionAmount.setScale(2, RoundingMode.HALF_UP);
        a.couponAmount = a.couponAmount.setScale(2, RoundingMode.HALF_UP);
        a.integrationAmount = a.integrationAmount.setScale(2, RoundingMode.HALF_UP);
        return a;
    }

    /**
     * 原子**锁定**库存（**仅 create 调用**，债务 5）：下单只预占，不动实物库存。
     *
     * <p>口径：{@code lock_stock = lock_stock + n WHERE id = ? AND stock - lock_stock >= n}
     * —— 判据是**可售**（stock − lock_stock）而不是总量。preview 绝不调用本方法。
     *
     * <p>失败直接抛异常：事务回滚会**连同本次循环里已经锁定成功的行一起回滚**
     * （同一本地事务），不会留下"锁了一半"的残留 —— 这就是不需要手动补偿的原因。
     */
    private void lockStock(List<ResolvedItem> rows) {
        for (ResolvedItem r : rows) {
            if (!skuStockService.lock(r.sku.getId(), r.quantity)) {
                throw new BusinessException("库存不足");
            }
        }
    }

    /**
     * 释放某订单占用的锁定库存（取消 / 超时关单共用）。
     *
     * <p>**必须**由「订单状态流转成功」的那一个线程调用 —— 独占性靠调用方的原子
     * 条件更新保证，本方法自身的 {@code lock_stock >= n} 条件只能兜住"减成负数"。
     * 释放失败只记告警、不抛异常：数据不一致不该阻塞用户取消订单。
     */
    private void releaseStock(Long orderId) {
        List<OrderItem> items = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, orderId));
        for (OrderItem it : items) {
            skuStockService.release(it.getSkuId(), it.getQuantity());
        }
    }

    /**
     * 由解析结果构建订单项（preview 传 orderSn=null，create 传真实单号）。
     * 取图口径与购物车一致：**优先 SKU 图，SKU 无图回退 SPU 商品图**。
     */
    private List<OrderItem> buildOrderItems(String orderSn, List<ResolvedItem> rows) {
        List<OrderItem> items = new ArrayList<>();
        for (ResolvedItem r : rows) {
            Sku sku = r.sku;
            Product product = r.product;
            OrderItem oi = new OrderItem();
            oi.setOrderSn(orderSn);
            oi.setSkuId(sku.getId());
            oi.setSkuCode(sku.getSkuCode());
            oi.setProductId(sku.getProductId());
            oi.setProductName(product != null ? product.getName() : "");
            // 本项目 SKU 多数无独立图，只取 sku.pic 会让订单项图存空 → 前端回退文字占位
            oi.setProductPic(StringUtils.hasText(sku.getPic())
                    ? sku.getPic()
                    : (product != null ? product.getPic() : null));
            oi.setProductSn(product != null ? product.getProductSn() : "");
            oi.setSpData(sku.getSpData());
            oi.setPrice(sku.getPrice());
            oi.setQuantity(r.quantity);
            items.add(oi);
        }
        return items;
    }


    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> pay(Long memberId, Long orderId) {
        Order o = orderMapper.selectById(orderId);
        if (o == null) return CommonResult.failed("订单不存在");
        if (!memberId.equals(o.getMemberId())) return CommonResult.failed("无权操作");
        // 2. 原子条件 UPDATE：仅当仍处于待支付(0)才置为已付(1)
        //    影响行数=0 说明订单已被支付/取消/超时关闭，拒绝并抛异常，避免覆盖
        LocalDateTime now = LocalDateTime.now();
        int rows = orderMapper.update(null, new LambdaUpdateWrapper<Order>()
                .eq(Order::getId, orderId)
                .eq(Order::getStatus, 0)
                .set(Order::getStatus, 1)
                .set(Order::getPaymentTime, now));
        if (rows == 0) {
            Order latest = orderMapper.selectById(orderId);
            if (latest != null && latest.getStatus() == 1) throw new BusinessException("订单已支付");
            throw new BusinessException("订单已关闭或不存在");
        }
        // 3. 支付成功即出库（债务 5）：把下单时的**预占**转为**真实扣减**
        //    stock -= n, lock_stock -= n —— 注意可售数量在支付前后**不变**（下单时已经减过了），
        //    所以这里绝不能改成只减 stock，否则同一件商品会被扣两次。
        //    与本方法的状态流转同事务：这里失败 → status 一起回滚，不会出现
        //    「已支付但库存没扣」的资损。
        List<OrderItem> items = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, orderId));
        for (OrderItem it : items) {
            if (!skuStockService.consume(it.getSkuId(), it.getQuantity())) {
                // 订单没有对应的锁定记录 → 数据/流程不一致，抛异常整单回滚并把问题暴露出来
                throw new BusinessException("库存扣减失败，请联系客服");
            }
        }
        // 4. 写入支付流水（幂等由 uk_order_id 兜底；此分支每个订单仅进入一次）
        Payment p = new Payment();
        p.setOrderId(orderId);
        p.setOrderSn(o.getOrderSn());
        p.setMemberId(memberId);
        p.setAmount(o.getPayAmount());
        p.setPayType(1);          // 1=mock
        p.setStatus(1);           // 1=已支付（mock 即时成功）
        p.setPayTime(Date.from(now.atZone(ZoneId.systemDefault()).toInstant()));
        paymentMapper.insert(p);

        // 支付成功后发布「新订单」事件到 Redis 频道，供后台管理端实时弹窗 + 语音提醒
        try {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("orderId", orderId);
            payload.put("orderSn", o.getOrderSn());
            payload.put("memberId", memberId);
            payload.put("totalAmount", o.getTotalAmount());
            payload.put("payAmount", o.getPayAmount());
            payload.put("createTime", o.getCreateTime() == null ? null : o.getCreateTime().toString());
            String json = new ObjectMapper().writeValueAsString(payload);
            // 用 StringCodec 发原始 JSON 字节，避免 Redisson 默认 codec 再包一层引号
            redisson.getTopic("mall:order:paid", StringCodec.INSTANCE).publish(json);
        } catch (Exception ex) {
            log.warn("发布新订单提醒事件失败（不影响支付结果）：{}", ex.getMessage());
        }

        recordHistory(o.getId(), o.getOrderSn(), "会员" + memberId, "PAY", "支付订单");
        return CommonResult.success(orderId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> cancel(Long memberId, Long orderId) {
        Order o = orderMapper.selectById(orderId);
        if (o == null) return CommonResult.failed("订单不存在");
        if (!memberId.equals(o.getMemberId())) return CommonResult.failed("无权操作");
        // 原子条件流转 0→4：并发双击只有一个线程 affected=1，其余拿到 0 直接返回。
        // 这一步是「释放库存独占」的**前提**：原写法是「selectById 判断 status，
        // 再 updateById 写」，两个并发请求都会读到 status=0 → 各自释放一次库存
        // → lock_stock 被减成负数（债务 5 顺手修的既有 bug）。
        int rows = orderMapper.update(null, new LambdaUpdateWrapper<Order>()
                .eq(Order::getId, orderId)
                .eq(Order::getStatus, 0)
                .set(Order::getStatus, 4)
                .set(Order::getCloseTime, LocalDateTime.now()));
        if (rows == 0) {
            Order latest = orderMapper.selectById(orderId);
            if (latest == null) return CommonResult.failed("订单不存在");
            if (latest.getStatus() != 0) return CommonResult.failed("订单状态已变更，请刷新后重试");
            return CommonResult.failed("取消失败，请稍后重试");
        }
        // 只有流转成功的线程走到这里 → 独占释放（只解除预占，不动实物库存）
        releaseStock(orderId);
        recordHistory(orderId, o.getOrderSn(), "会员" + memberId, "CANCEL", "取消订单");
        return CommonResult.success(orderId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> confirmReceived(Long memberId, Long orderId) {
        Order o = orderMapper.selectById(orderId);
        if (o == null) return CommonResult.failed("订单不存在");
        if (!memberId.equals(o.getMemberId())) return CommonResult.failed("无权操作");
        return completeOrder(orderId, "会员" + memberId)
                ? CommonResult.success(orderId)
                : CommonResult.failed("仅已发货订单可确认收货");
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean completeOrder(Long orderId, String operator) {
        Order o = orderMapper.selectById(orderId);
        if (o == null) return false;
        // 原子条件流转 2→3：仅当仍为「已发货」才成功。并发/重复请求 affected=0，
        // 既防重复确认，也保证下方"赠送积分"每单只执行一次（债务18 幂等）
        int rows = orderMapper.update(null, new LambdaUpdateWrapper<Order>()
                .eq(Order::getId, orderId)
                .eq(Order::getStatus, 2)
                .set(Order::getStatus, 3)
                .set(Order::getReceiveTime, LocalDateTime.now()));
        if (rows == 0) return false;
        // 交易完成 → 按实付金额赠送积分与成长值（等级积分倍率），成长值达门槛自动升级
        memberPointsService.grantForOrder(o.getMemberId(), orderId, o.getOrderSn(), o.getPayAmount());
        recordHistory(o.getId(), o.getOrderSn(),
                operator == null || operator.isBlank() ? "system" : operator,
                "CONFIRM", "确认收货");
        return true;
    }

    @Override
    public CommonResult<CommonPage<Order>> listOrders(Long memberId, Integer status, Integer pageNum, Integer pageSize) {
        IPage<Order> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Order> w = new LambdaQueryWrapper<>();
        w.eq(Order::getMemberId, memberId);
        if (status != null) w.eq(Order::getStatus, status);
        w.orderByDesc(Order::getCreateTime);
        return CommonResult.success(CommonPage.restPage(orderMapper.selectPage(page, w)));
    }

    @Override
    public CommonResult<OrderDetailVO> detail(Long memberId, Long orderId) {
        Order o = orderMapper.selectById(orderId);
        if (o == null) return CommonResult.failed("订单不存在");
        if (!memberId.equals(o.getMemberId())) return CommonResult.failed("无权操作");
        List<OrderItem> items = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, orderId));
        OrderDetailVO vo = new OrderDetailVO();
        vo.setOrder(o);
        vo.setItems(items);
        return CommonResult.success(vo);
    }

    /**
     * 系统触发：超时自动取消（幂等）。仅当订单仍处于待支付(0) 才取消，
     * 已支付/已取消等状态直接跳过，避免误取消已支付订单。
     *
     * <p>债务 5 后语义变化：取消只**释放预占**（{@code lock_stock -= n}），不再加回
     * {@code stock} —— 下单时压根没减过实物库存。实物库存只在支付（consume）与
     * 作废（restore）两处动。
     */
    @Transactional(rollbackFor = Exception.class)
    public void cancelExpiredBySystem(Long orderId) {
        // 1. 原子更新订单状态（乐观锁）
        int affected = orderMapper.update(null, new LambdaUpdateWrapper<Order>()
                .eq(Order::getId, orderId)
                .eq(Order::getStatus, 0)           // 关键：只有待支付才能取消
                .set(Order::getStatus, 4)
                .set(Order::getCloseTime, LocalDateTime.now()));

        if (affected == 0) {
            log.info("订单不存在或状态已变更，跳过: orderId={}", orderId);
            return;  // 重要：直接返回，不释放库存（延迟消息重复投递会走到这里）
        }

        // 2. 只有更新成功的线程才释放预占 —— 原子 0→4 保证同一订单只释放一次
        releaseStock(orderId);

        log.info("订单超时取消成功: orderId={}", orderId);
    }

    /**
     * 债务7 / 18：把三类整单优惠（会员折扣 promotion、优惠券 coupon、积分抵扣 integration）
     * 分别按"本行原价小计 / 全单原价小计"的比例分摊到每个 order_item，
     * 写回 promotion_amount / coupon_amount / integration_amount，并算出 real_amount。
     * 每类优惠前 n-1 行四舍五入、尾行吸收余数，保证各类 Σ 分摊 == 该类整单优惠额。
     * 全程 BigDecimal，禁止浮点；real_amount 不含运费（运费是否退单独处理）。
     */
    private void allocateDiscount(List<OrderItem> items, BigDecimal promotion,
                                  BigDecimal coupon, BigDecimal integration) {
        if (items == null || items.isEmpty()) return;
        BigDecimal sumLine = BigDecimal.ZERO;
        for (OrderItem oi : items) {
            sumLine = sumLine.add(oi.getPrice().multiply(BigDecimal.valueOf(oi.getQuantity())));
        }
        if (sumLine.compareTo(BigDecimal.ZERO) <= 0) {               // 极端：无金额，全 0
            for (OrderItem oi : items) {
                oi.setPromotionAmount(BigDecimal.ZERO);
                oi.setCouponAmount(BigDecimal.ZERO);
                oi.setIntegrationAmount(BigDecimal.ZERO);
                oi.setRealAmount(BigDecimal.ZERO);
            }
            return;
        }
        BigDecimal[] promoAlloc = distribute(items, promotion, sumLine);
        BigDecimal[] couponAlloc = distribute(items, coupon, sumLine);
        BigDecimal[] integAlloc = distribute(items, integration, sumLine);
        for (int i = 0; i < items.size(); i++) {
            OrderItem oi = items.get(i);
            BigDecimal line = oi.getPrice().multiply(BigDecimal.valueOf(oi.getQuantity()));
            oi.setPromotionAmount(promoAlloc[i]);
            oi.setCouponAmount(couponAlloc[i]);
            oi.setIntegrationAmount(integAlloc[i]);
            BigDecimal real = line.subtract(promoAlloc[i]).subtract(couponAlloc[i]).subtract(integAlloc[i]);
            if (real.compareTo(BigDecimal.ZERO) < 0) real = BigDecimal.ZERO;   // 防御：叠加优惠后不为负
            oi.setRealAmount(real.setScale(2, RoundingMode.HALF_UP));
        }
    }

    /**
     * 把某一类整单优惠额按"本行原价小计"比例分摊为数组（前 n-1 行四舍五入，尾行吸收余数）。
     * 各类优惠额均不超过商品总额，故单行分摊不会超过本行原价（保留防御性封顶）。
     */
    private BigDecimal[] distribute(List<OrderItem> items, BigDecimal whole, BigDecimal sumLine) {
        int n = items.size();
        BigDecimal[] out = new BigDecimal[n];
        for (int i = 0; i < n; i++) out[i] = BigDecimal.ZERO;
        if (whole == null || whole.compareTo(BigDecimal.ZERO) <= 0) return out;

        BigDecimal allocatedSum = BigDecimal.ZERO;
        for (int i = 0; i < n; i++) {
            OrderItem oi = items.get(i);
            BigDecimal line = oi.getPrice().multiply(BigDecimal.valueOf(oi.getQuantity()));
            BigDecimal alloc;
            if (i == n - 1) {
                alloc = whole.subtract(allocatedSum);                // 尾行吸收四舍五入余数
            } else {
                BigDecimal ratio = line.divide(sumLine, 10, RoundingMode.HALF_UP);
                alloc = whole.multiply(ratio).setScale(2, RoundingMode.HALF_UP);
                allocatedSum = allocatedSum.add(alloc);
            }
            if (alloc.compareTo(BigDecimal.ZERO) < 0) alloc = BigDecimal.ZERO;   // 防御
            if (alloc.compareTo(line) > 0) alloc = line;                        // 封顶：不超过本行原价
            out[i] = alloc;
        }
        return out;
    }

    private String getOrderSn() {
        String date = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        String key = "order:sn:" + date;
        RAtomicLong atomic = redisson.getAtomicLong(key);
        long seq = atomic.incrementAndGet();
        atomic.expire(24, TimeUnit.HOURS); // 每日 key 24h 后过期
        return "O" + date + String.format("%06d", seq);
    }

    private void recordHistory(Long orderId, String orderSn, String man, String type, String note) {
        OrderOperateHistory h = new OrderOperateHistory();
        h.setOrderId(orderId);
        h.setOrderSn(orderSn);
        h.setOperateMan(man);
        h.setOperateType(type);
        h.setOperateNote(note == null ? "" : note);
        historyMapper.insert(h);
    }
}
