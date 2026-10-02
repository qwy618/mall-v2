package com.macro.mall.common.exception;

import com.macro.mall.common.CommonResult;
import com.macro.mall.common.ResultCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.validation.BindException;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * 全局异常处理器
 *
 * <p>三分法（日志级别决定要不要触发告警，不能一刀切 error）：
 * <ul>
 *   <li>业务异常     → 返回原始 message（用户该看见），warn，不打堆栈</li>
 *   <li>参数校验失败 → 返回字段级错误，warn，不打堆栈</li>
 *   <li>未知异常     → 固定兜底文案（防信息泄露），error + 完整堆栈</li>
 * </ul>
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * 业务异常：预期内的失败（库存不足、商品已下架），不该触发告警
     */
    @ExceptionHandler(BusinessException.class)
    public CommonResult<Void> handleBusinessException(BusinessException e) {
        log.warn("业务异常：code={}, message={}", e.getCode(), e.getMessage());
        return CommonResult.failed(e.getCode(), e.getMessage());
    }

    /**
     * 参数校验失败。
     *
     * <p>只写这一个就够：Spring 6 中 {@code MethodArgumentNotValidException extends BindException}
     * （已用 javap 验证 spring-web 6.2.18），Spring 会按继承链匹配最近的处理方法，
     * 所以 @RequestBody 校验失败和表单绑定失败都会走到这里。
     */
    @ExceptionHandler(BindException.class)
    public CommonResult<Void> handleBindException(BindException e) {
        String message = resolveValidateMessage(e.getBindingResult());
        log.warn("参数校验失败：{}", message);
        return CommonResult.validateFailed(message);
    }

    /**
     * 资源不存在（接口路径写错 / 静态文件缺失 / favicon.ico）。
     *
     * <p>Spring Boot 3.2+ 会抛 NoResourceFoundException。如果不单独处理，它会被下面的
     * 兜底 handler 接住，导致：① 404 被伪装成 500；② 浏览器每请求一次 favicon.ico
     * 就刷一条 ERROR 堆栈，日志很快被噪音淹没。
     *
     * <p>不打日志：调用方路径写错是常态，不值得占用错误日志。
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public CommonResult<Void> handleNoResourceFoundException(NoResourceFoundException e) {
        return CommonResult.failed(ResultCode.NOT_FOUND, "资源不存在：" + e.getResourcePath());
    }

    /**
     * 兜底：未知异常。
     *
     * <p>注意不要把 e.getMessage() 返回给前端 —— 里面可能是完整 SQL、表名、内网 IP。
     */
    @ExceptionHandler(Exception.class)
    public CommonResult<Void> handleException(Exception e) {
        log.error("系统异常：", e);
        return CommonResult.failed("系统繁忙，请稍后再试");
    }
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public CommonResult<Void> handleTypeMismatch(MethodArgumentTypeMismatchException e) {
        String message = String.format("参数 '%s' 类型错误，期望类型：%s",
                e.getName(),
                e.getRequiredType().getSimpleName());
        log.warn("参数类型不匹配：{}", message);
        return CommonResult.validateFailed(message);
    }

    private String resolveValidateMessage(BindingResult bindingResult) {
        FieldError fieldError = bindingResult.getFieldError();
        if (fieldError == null) {
            return "参数校验失败";
        }
        return fieldError.getField() + "：" + fieldError.getDefaultMessage();
    }
}
