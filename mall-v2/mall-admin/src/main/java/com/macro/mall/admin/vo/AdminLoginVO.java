package com.macro.mall.admin.vo;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor   // 生成 AdminLoginVO(String token, String tokenHead)
@NoArgsConstructor    // 保留无参，序列化/框架反射需要
public class AdminLoginVO {
    private String token;
    private String tokenHead;
}