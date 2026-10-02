package com.macro.mall.common;

public class ResultCode {
   public static final Integer SUCCESS = 200;
    /** 失败 */
    public static final Integer FAILED = 500;

    /** 参数校验失败 */
    public static final Integer VALIDATE_FAILED = 400;

    /** 未登录 */
    public static final Integer UNAUTHORIZED = 401;

    /** 数据不存在*/
    public static final Integer NOT_FOUND = 404;

    /** 未授权 */
    public static final Integer FORBIDDEN = 403;

    /** 业务异常 */
    public static final Integer BUSINESS_ERROR = 600;

    /** 系统异常 */
    public static final Integer SYSTEM_ERROR = 700;

}
