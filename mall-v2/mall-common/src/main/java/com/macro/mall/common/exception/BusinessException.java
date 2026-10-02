package com.macro.mall.common.exception;

import com.macro.mall.common.ResultCode;

public class BusinessException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    /** 错误码 */
    private Integer code;

    /**
     * 只传消息，使用默认错误码
     */
    public BusinessException(String message) {
        super(message);
        this.code = ResultCode.BUSINESS_ERROR;
    }

    /**
     * 传错误码 + 消息
     */
    public BusinessException(Integer code, String message) {
        super(message);
        this.code = code;
    }

    /**
     * 传消息 + 原因
     */
    public BusinessException(String message, Throwable cause) {
        super(message, cause);
        this.code = ResultCode.BUSINESS_ERROR;
    }

    /**
     * 传错误码 + 消息 + 原因
     */
    public BusinessException(Integer code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    public Integer getCode() {
        return code;
    }

    public void setCode(Integer code) {
        this.code = code;
    }
}
