package com.macro.mall.mbg.mapper;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.macro.mall.mbg.model.Order;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

public interface OrderMapper extends BaseMapper<Order> {
    /**
     * 看板时序：按日聚合订单数 + 销售额（pay_amount 求和）。
     * 仅统计未逻辑删除（delete_status=0）且 create_time >= start 的订单。
     * 返回 Map 避免额外 DTO：order_date=LocalDate(Date)、order_count=Long、order_amount=BigDecimal。
     */
    @Select("SELECT DATE(create_time) AS order_date, COUNT(*) AS order_count, COALESCE(SUM(pay_amount),0) AS order_amount " +
            "FROM orders WHERE delete_status = 0 AND create_time >= #{start} " +
            "GROUP BY DATE(create_time) ORDER BY order_date")
    List<Map<String, Object>> selectTrend(@Param("start") LocalDateTime start);
}
// OrderItemMapper 同理，把 Order 换成 OrderItem
