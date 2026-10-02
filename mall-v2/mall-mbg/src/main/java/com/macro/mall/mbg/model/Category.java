package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("category")
public class Category {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String name;
    private Long parentId;
    private Integer level;
    private Integer sort;
    private String icon;
    private Integer showStatus;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private Integer deleteStatus;
}
