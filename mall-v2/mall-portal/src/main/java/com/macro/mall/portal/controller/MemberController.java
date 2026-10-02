package com.macro.mall.portal.controller;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.model.Member;
import com.macro.mall.mbg.model.MemberIntegrationHistory;
import com.macro.mall.portal.component.JwtTokenUtil;
import com.macro.mall.portal.component.MemberAuth;
import com.macro.mall.portal.service.MemberService;
import com.macro.mall.portal.vo.LoginResultVO;
import com.macro.mall.service.MemberLevelService;
import com.macro.mall.service.MemberPointsService;
import com.macro.mall.service.vo.MemberLevelVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;

@RestController
@RequestMapping("/member")
public class MemberController {

    @Autowired
    private MemberService memberService;
    @Autowired
    private JwtTokenUtil jwtTokenUtil;
    @Autowired
    private HttpServletRequest request;
    @Autowired
    private MemberAuth memberAuth;
    @Autowired
    private MemberLevelService memberLevelService;
    @Autowired
    private MemberPointsService memberPointsService;

    @PostMapping("/register")
    public CommonResult<Long> register(@RequestParam String phone,
                                       @RequestParam String password,
                                       @RequestParam(required = false) String nickname) {
        return CommonResult.success(memberService.register(phone, password, nickname));
    }

    @PostMapping("/login")
    public CommonResult<LoginResultVO> login(@RequestParam String phone,
                                            @RequestParam String password) {
        return CommonResult.success(memberService.login(phone, password));
    }

    @GetMapping("/info")
    public CommonResult<Member> info() {
        return CommonResult.success(memberService.getCurrentMember(resolvePhone()));
    }

    @PostMapping("/updatePassword")
    public CommonResult<Void> updatePassword(@RequestParam String oldPassword,
                                             @RequestParam String newPassword) {
        memberService.updatePassword(resolvePhone(), oldPassword, newPassword);
        return CommonResult.success(null);
    }

    @PostMapping("/updateIcon")
    public CommonResult<Void> updateIcon(@RequestParam String icon) {
        memberService.updateIcon(resolvePhone(), icon);
        return CommonResult.success(null);
    }

    /** 会员等级/成长信息（债务18）：等级名、权益、成长进度、可用与累计积分 */
    @GetMapping("/level")
    public CommonResult<MemberLevelVO> level() {
        Member m = memberService.getById(memberAuth.memberId());
        return CommonResult.success(memberLevelService.buildVO(m));
    }

    /** 积分流水（债务18）：倒序分页，含变动类型/数额/变动后余额 */
    @GetMapping("/integration/list")
    public CommonResult<CommonPage<MemberIntegrationHistory>> integrationList(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {
        return CommonResult.success(
                memberPointsService.listHistory(memberAuth.memberId(), pageNum, pageSize));
    }

    /** 从 Authorization: Bearer xxx 解析出当前会员手机号 */
    private String resolvePhone() {
        String auth = request.getHeader("Authorization");
        if (auth == null || !auth.startsWith("Bearer ")) {
            throw new BusinessException("未登录或登录已过期");
        }
        return jwtTokenUtil.getUsernameFromToken(auth.substring(7));
    }
}
