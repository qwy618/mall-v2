package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.dto.OrderItemParam;
import com.macro.mall.admin.dto.OrderParam;
import com.macro.mall.admin.dto.OrderShipParam;
import com.macro.mall.admin.dto.SkuParam;
import com.macro.mall.admin.service.OrderService;
import com.macro.mall.admin.vo.OrderDetailVO;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.*;
import com.macro.mall.mbg.model.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.util.StringUtils;
import com.macro.mall.admin.component.AdminUserDetails;
import com.macro.mall.service.MemberPointsService;

import java.math.BigDecimal;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;

@Service
public class OrderServiceImpl implements OrderService {
    @Autowired
    private MemberAddressMapper memberAddressMapper;
    @Autowired
    private StringRedisTemplate redisTemplate;
    @Autowired
    private SkuMapper skuMapper;
    @Autowired
    private ProductMapper productMapper;
    @Autowired
    private OrderMapper orderMapper;
    @Autowired
    private OrderItemMapper orderItemMapper;
    @Autowired
    private OrderOperateHistoryMapper historyMapper;
    @Autowired
    private CouponHistoryMapper couponHistoryMapper;
    @Autowired
    private PaymentMapper paymentMapper;
    @Autowired
    private MemberPointsService memberPointsService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> createOrder(OrderParam param)  {
        //1.查询地址是否存在
        MemberAddress memberAddress = memberAddressMapper.selectById(param.getAddressId());
        if (memberAddress == null) {
            return CommonResult.validateFailed("地址不存在");
        }
        //2.生成订单编号用redis
        String orderSn = getOrderSn();
        //3.判断运费
        BigDecimal freight = param.getFreightAmount() == null ? BigDecimal.ZERO : param.getFreightAmount();
        BigDecimal total = BigDecimal.ZERO;
        List<OrderItem> items = new ArrayList<>();
        //4.拿到订单项
        for(OrderItemParam item : param.getItems()){
            if(item.getQuantity() <= 0){
                throw new BusinessException("数量必须大于0");
            }
            Sku sku = skuMapper.selectById(item.getSkuId());
            if(sku == null){
                throw new BusinessException("商品不存在");   // ← 抛异常，事务回滚
            }
            //5.乐观锁扣减商品
            LambdaUpdateWrapper<Sku> updateWrapper = new LambdaUpdateWrapper<>();
            updateWrapper.eq(Sku::getId, item.getSkuId())
                    .ge(Sku::getStock, item.getQuantity())
                    .setSql("stock = stock - " + item.getQuantity());
            int update = skuMapper.update(null, updateWrapper);
            if (update == 0) {
                throw new BusinessException("库存不足");
            }
            //6.获取商品
            Product product = productMapper.selectById(sku.getProductId());
            OrderItem oi = new OrderItem();
            oi.setOrderSn(orderSn);
            oi.setSkuId(sku.getId());
            oi.setSkuCode(sku.getSkuCode());
            oi.setProductId(sku.getProductId());
            oi.setProductName(product != null ? product.getName() : "");
            oi.setProductPic(sku.getPic());
            oi.setProductSn(product != null ? product.getProductSn() : "");
            oi.setSpData(sku.getSpData());
            oi.setPrice(sku.getPrice());           // 价格以库里 sku 为准，不信前端
            oi.setQuantity(item.getQuantity());
            items.add(oi);
            total = total.add(sku.getPrice().multiply(BigDecimal.valueOf(item.getQuantity())));
        }
        Order order = new Order();
        order.setOrderSn(orderSn);
        order.setMemberId(param.getMemberId());
        order.setAddressId(param.getAddressId());
        order.setTotalAmount(total.add(freight));
        order.setPayAmount(total.add(freight));
        order.setFreightAmount(freight);
        order.setStatus(0);                        // 0 待付款
        order.setReceiverName(memberAddress.getReceiverName());
        order.setReceiverPhone(memberAddress.getPhone());
        order.setReceiverProvince(memberAddress.getProvince());
        order.setReceiverCity(memberAddress.getCity());
        order.setReceiverDistrict(memberAddress.getDistrict());
        order.setReceiverDetailAddress(memberAddress.getDetailAddress());
        orderMapper.insert(order);
        Long orderId = order.getId();

        items.forEach(oi -> oi.setOrderId(orderId));
        orderItemMapper.insertBatch(items);
        return CommonResult.success(orderId);
    }

    @Override
    public CommonResult<CommonPage<Order>> listOrders(Integer pageNum, Integer pageSize, Integer status, Long memberId, String keyword) {
        IPage<Order> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Order> w = new LambdaQueryWrapper<>();
        if (status != null) w.eq(Order::getStatus, status);
        if (memberId != null) w.eq(Order::getMemberId, memberId);
        if (StringUtils.hasText(keyword)) w.like(Order::getOrderSn, keyword);
        w.orderByDesc(Order::getCreateTime);   // 最新订单排最前
        return CommonResult.success(CommonPage.restPage(orderMapper.selectPage(page, w)));
    }

    @Override
    public CommonResult<OrderDetailVO> detail(Long id) {
        Order order = orderMapper.selectById(id);
        if (order == null) return CommonResult.failed("订单不存在");
        List<OrderItem> items = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, id));
        OrderDetailVO vo = new OrderDetailVO();
        vo.setOrder(order);
        vo.setItems(items);
        return CommonResult.success(vo);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> pay(Long id) {
        Order o = orderMapper.selectById(id);
        if (o == null) return CommonResult.failed("订单不存在");
        if (o.getStatus() != 0) throw new BusinessException("仅待付款订单可支付");
        o.setStatus(1);
        o.setPaymentTime(LocalDateTime.now());
        orderMapper.updateById(o);
        return CommonResult.success(id);
    }

    @Override
    public CommonResult<Long> ship(Long id, OrderShipParam param) {
        Order o = orderMapper.selectById(id);
        if (o == null) return CommonResult.failed("订单不存在");
        if (o.getStatus() != 1) throw new BusinessException("仅已付款订单可发货");
        o.setStatus(2);
        o.setDeliveryCompany(param.getDeliveryCompany());
        o.setDeliverySn(param.getDeliverySn());
        o.setDeliveryTime(LocalDateTime.now());
        orderMapper.updateById(o);
        recordHistory(o.getId(), o.getOrderSn(), currentAdmin(), "SHIP",
                "发货：" + (param.getDeliveryCompany() == null ? "" : param.getDeliveryCompany())
                        + " " + (param.getDeliverySn() == null ? "" : param.getDeliverySn()));
        return CommonResult.success(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> complete(Long id) {
        Order o = orderMapper.selectById(id);
        if (o == null) return CommonResult.failed("订单不存在");
        // 原子条件流转 2→3：防并发/重复点击，也保证下方"赠送积分"每单只执行一次
        int rows = orderMapper.update(null, new LambdaUpdateWrapper<Order>()
                .eq(Order::getId, id)
                .eq(Order::getStatus, 2)
                .set(Order::getStatus, 3)
                .set(Order::getReceiveTime, LocalDateTime.now()));
        if (rows == 0) return CommonResult.failed("仅已发货订单可确认收货");
        // 后台代确认收货同样按实付赠送积分/成长值（与 C 端确认收货共用共享逻辑，避免口径漂移）
        memberPointsService.grantForOrder(o.getMemberId(), id, o.getOrderSn(), o.getPayAmount());
        recordHistory(o.getId(), o.getOrderSn(), currentAdmin(), "CONFIRM", "确认收货");
        return CommonResult.success(id);
    }

    /**
     * 作废订单（债务8，状态 5=无效订单）：仅「已付款但尚未发货」的订单可作废。
     * 与「取消（4=已关闭）」的区别：取消针对待付款单，作废针对已付款却无法履约的单。
     * 作废时要一次性把该单的副作用全部回滚，否则会出现"钱退了但库存/券/积分没回来"的资损。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> invalidate(Long id, String note) {
        Order o = orderMapper.selectById(id);
        if (o == null) return CommonResult.failed("订单不存在");
        // 原子条件流转 1→5：仅当仍处于已付款(1) 才成功，重复点击 affected=0 自然幂等
        int rows = orderMapper.update(null, new LambdaUpdateWrapper<Order>()
                .eq(Order::getId, id)
                .eq(Order::getStatus, 1)
                .set(Order::getStatus, 5)
                .set(Order::getCloseTime, LocalDateTime.now()));
        if (rows == 0) return CommonResult.failed("仅已付款（未发货）订单可作废");

        // 1. 回滚库存：逐 item 把下单扣掉的 quantity 加回 sku.stock
        List<OrderItem> items = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, id));
        for (OrderItem item : items) {
            skuMapper.update(null, new LambdaUpdateWrapper<Sku>()
                    .eq(Sku::getId, item.getSkuId())
                    .setSql("stock = stock + " + item.getQuantity()));
        }

        // 2. 退回优惠券：把本单核销的记录改回未使用，会员可再次使用
        couponHistoryMapper.update(null, new LambdaUpdateWrapper<CouponHistory>()
                .eq(CouponHistory::getOrderId, id)
                .eq(CouponHistory::getStatus, 1)
                .set(CouponHistory::getStatus, 0)
                .set(CouponHistory::getOrderId, null)
                .set(CouponHistory::getOrderSn, null)
                .set(CouponHistory::getUseTime, null));

        // 3. 退回下单时抵扣的积分
        if (o.getUseIntegration() != null && o.getUseIntegration() > 0) {
            memberPointsService.refundConsumed(o.getMemberId(), id, o.getOrderSn(), o.getUseIntegration());
        }

        // 4. 退款（Mock：无真实支付通道，仅把支付流水标记为已退款并记录金额/时间）
        paymentMapper.update(null, new LambdaUpdateWrapper<Payment>()
                .eq(Payment::getOrderId, id)
                .eq(Payment::getStatus, 1)
                .set(Payment::getStatus, 2)
                .set(Payment::getRefundAmount, o.getPayAmount())
                .set(Payment::getRefundTime,
                        Date.from(LocalDateTime.now().atZone(ZoneId.systemDefault()).toInstant())));

        recordHistory(o.getId(), o.getOrderSn(), currentAdmin(), "INVALIDATE",
                "订单作废并退款￥" + o.getPayAmount() + (note == null || note.isBlank() ? "" : "（" + note + "）"));
        return CommonResult.success(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Long> cancel(Long id) {
        Order o = orderMapper.selectById(id);
        if (o == null) return CommonResult.failed("订单不存在");
        if (o.getStatus() != 0) return CommonResult.failed("仅待付款订单可取消");
        // 还原库存：逐 item 把下单扣的 quantity 加回 sku.stock
        List<OrderItem> items = orderItemMapper.selectList(
                new LambdaQueryWrapper<OrderItem>().eq(OrderItem::getOrderId, id));
        for (OrderItem item : items) {
            skuMapper.update(null, new LambdaUpdateWrapper<Sku>()
                    .eq(Sku::getId, item.getSkuId())
                    .setSql("stock = stock + " + item.getQuantity()));
        }
        o.setStatus(4);
        o.setCloseTime(LocalDateTime.now());
        orderMapper.updateById(o);
        recordHistory(o.getId(), o.getOrderSn(), currentAdmin(), "CANCEL", "取消订单");
        return CommonResult.success(id);
    }

    @Override
    public CommonResult<Long> delete(Long id) {
        return CommonResult.success((long) orderMapper.deleteById(id));
    }

    private String getOrderSn() {
        String date = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        String key = "order:sn:" + date;
        Long seq = redisTemplate.opsForValue().increment(key);
        if (seq != null && seq == 1) {
            redisTemplate.expire(key, Duration.ofDays(1)); // 每日 key 过期，不无限堆积
        }
        return "O" + date + String.format("%06d", seq == null ? 0 : seq);
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

    private String currentAdmin() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof AdminUserDetails d) {
            return d.getUsername();
        }
        return "admin";
    }
}
