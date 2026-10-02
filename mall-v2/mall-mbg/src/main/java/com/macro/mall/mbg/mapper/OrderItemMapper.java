package com.macro.mall.mbg.mapper;
import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.macro.mall.mbg.model.OrderItem;
import org.apache.ibatis.annotations.Param;

import java.util.List;

public interface OrderItemMapper extends BaseMapper<OrderItem> {
    /**
     * 批量插入
     */
    int insertBatch(@Param("list") List<OrderItem> list);
}

