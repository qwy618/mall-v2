package com.macro.mall.mbg.model;

import java.time.LocalDateTime;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("brand")
public class Brand {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String name;
    private String description;
    private String logo;
    private Integer sort;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private Integer deleteStatus;
}
