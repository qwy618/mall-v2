package com.macro.mall.common;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@AllArgsConstructor
@NoArgsConstructor
@Data
public class CommonResult <T> {
    private Integer code;
    private String message;
    private T data;
    public static <T> CommonResult<T> success(T data) {
        return new CommonResult<>(ResultCode.SUCCESS, "操作成功", data);
    }

    /**
     * 成功（带消息 + 数据）
     */
    public static <T> CommonResult<T> success(String message, T data) {
        return new CommonResult<>(ResultCode.SUCCESS, message, data);
    }

    /**
     * 成功（无数据）
     */
    public static <T> CommonResult<T> success() {
        return new CommonResult<>(ResultCode.SUCCESS, "操作成功", null);
    }

    /**
     * 失败（默认 code）
     */
    public static <T> CommonResult<T> failed(String message) {
        return new CommonResult<>(ResultCode.FAILED, message, null);
    }

    /**
     * 失败（自定义 code）
     */
    public static <T> CommonResult<T> failed(Integer code, String message) {
        return new CommonResult<>(code, message, null);
    }

    /**
     * 参数校验失败
     */
    public static <T> CommonResult<T> validateFailed(String message) {
        return new CommonResult<>(ResultCode.VALIDATE_FAILED, message, null);
    }

    /**
     * 未登录
     */
    public static <T> CommonResult<T> unauthorized(T data) {
        return new CommonResult<>(ResultCode.UNAUTHORIZED, "暂未登录或token已经过期", data);
    }

    /**
     * 未登录（无数据）—— 阶段 4 鉴权时最高频的调用，不重载就得每次写 unauthorized(null)
     */
    public static <T> CommonResult<T> unauthorized() {
        return unauthorized(null);
    }

    /**
     * 未授权
     */
    public static <T> CommonResult<T> forbidden(T data) {
        return new CommonResult<>(ResultCode.FORBIDDEN, "没有相关权限", data);
    }

    /**
     * 未授权（无数据）
     */
    public static <T> CommonResult<T> forbidden() {
        return forbidden(null);
    }

}
