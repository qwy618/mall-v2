package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.CommentMapper;
import com.macro.mall.mbg.mapper.MemberMapper;
import com.macro.mall.mbg.mapper.OrderItemMapper;
import com.macro.mall.mbg.mapper.OrderMapper;
import com.macro.mall.mbg.model.Comment;
import com.macro.mall.mbg.model.Member;
import com.macro.mall.mbg.model.Order;
import com.macro.mall.mbg.model.OrderItem;
import com.macro.mall.portal.dao.CommentSubmitParam;
import com.macro.mall.portal.service.CommentService;
import com.macro.mall.portal.vo.CommentStatsVO;
import com.macro.mall.portal.vo.ProductCommentVO;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 商品评价服务实现（C 端）。
 *
 * 校验点：
 *  - 订单项归属当前会员（防越权）
 *  - 订单须为「已完成/已收货」(status=3) 才能评价
 *  - 同一订单项不可重复评价（DB order_item_id 唯一约束 + 前置查询双保险）
 *  - 匿名评价时清空昵称 / 头像
 */
@Service
public class CommentServiceImpl implements CommentService {

    private static final int ORDER_FINISHED = 3;   // 订单状态：已完成/已收货
    private static final int STATUS_PENDING = 0;   // 评价状态：待审核
    private static final int STATUS_APPROVED = 1;  // 评价状态：通过

    @Autowired private CommentMapper commentMapper;
    @Autowired private OrderItemMapper orderItemMapper;
    @Autowired private OrderMapper orderMapper;
    @Autowired private MemberMapper memberMapper;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Void> submit(Long memberId, CommentSubmitParam param) {
        OrderItem oi = orderItemMapper.selectById(param.getOrderItemId());
        if (oi == null) {
            return CommonResult.failed("订单项不存在");
        }
        Order order = orderMapper.selectById(oi.getOrderId());
        if (order == null || !memberId.equals(order.getMemberId())) {
            return CommonResult.failed("无权评价该订单");
        }
        if (order.getStatus() == null || order.getStatus() != ORDER_FINISHED) {
            return CommonResult.failed("订单未完成，暂不能评价");
        }
        // 重复评价双保险：DB 还有 order_item_id 唯一约束
        Long existing = commentMapper.selectCount(new LambdaQueryWrapper<Comment>()
                .eq(Comment::getOrderItemId, param.getOrderItemId()));
        if (existing != null && existing > 0) {
            return CommonResult.failed("该订单项已评价");
        }

        Member member = memberMapper.selectById(memberId);

        boolean anonymous = Boolean.TRUE.equals(param.getAnonymous());
        Comment c = new Comment();
        c.setOrderItemId(oi.getId());
        c.setOrderId(oi.getOrderId());
        c.setOrderSn(oi.getOrderSn());
        c.setProductId(oi.getProductId());
        c.setSkuId(oi.getSkuId());
        c.setProductName(oi.getProductName());
        c.setProductPic(oi.getProductPic());
        c.setMemberId(memberId);
        c.setStar(param.getStar());
        c.setContent(param.getContent());
        try {
            c.setPics(param.getPics() == null ? null :
                    objectMapper.writeValueAsString(param.getPics()));
        } catch (Exception e) {
            throw new BusinessException("图片数据处理失败");
        }
        c.setAnonymous(anonymous ? 1 : 0);
        if (anonymous) {
            c.setMemberNickname(null);
            c.setMemberIcon(null);
        } else if (member != null) {
            c.setMemberNickname(member.getNickname());
            c.setMemberIcon(member.getIcon());
        }
        c.setStatus(STATUS_PENDING);
        c.setCreateTime(new Date());
        commentMapper.insert(c);

        // 标记订单项已评价（冗余字段，订单列表直接显示「已评价」免联表）
        OrderItem upd = new OrderItem();
        upd.setId(oi.getId());
        upd.setCommentStatus(1);
        orderItemMapper.updateById(upd);

        return CommonResult.success();
    }

    @Override
    public CommonResult<CommonPage<ProductCommentVO>> listProductComments(Long productId, int pageNum, int pageSize) {
        IPage<Comment> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Comment> w = new LambdaQueryWrapper<>();
        w.eq(Comment::getProductId, productId);
        w.eq(Comment::getStatus, STATUS_APPROVED);
        w.orderByDesc(Comment::getCreateTime);
        IPage<Comment> result = commentMapper.selectPage(page, w);
        CommonPage<ProductCommentVO> cp = new CommonPage<>();
        cp.setPageNum((int) result.getCurrent());
        cp.setPageSize((int) result.getSize());
        cp.setTotal(result.getTotal());
        cp.setTotalPage((int) ((result.getTotal() + result.getSize() - 1) / result.getSize()));
        cp.setList(result.getRecords().stream().map(this::toVO).collect(Collectors.toList()));
        return CommonResult.success(cp);
    }

    @Override
    public CommonResult<CommentStatsVO> getStats(Long productId) {
        CommentStatsVO vo = new CommentStatsVO();
        Long total = commentMapper.selectCount(new LambdaQueryWrapper<Comment>()
                .eq(Comment::getProductId, productId)
                .eq(Comment::getStatus, STATUS_APPROVED));
        vo.setTotal(total == null ? 0L : total);
        vo.setFiveStar(countStar(productId, 5));
        vo.setFourStar(countStar(productId, 4));
        vo.setThreeStar(countStar(productId, 3));
        vo.setTwoStar(countStar(productId, 2));
        vo.setOneStar(countStar(productId, 1));
        double sum = 5 * vo.getFiveStar() + 4 * vo.getFourStar() + 3 * vo.getThreeStar()
                + 2 * vo.getTwoStar() + 1 * vo.getOneStar();
        double avg = vo.getTotal() == 0 ? 0.0 : sum / vo.getTotal();
        vo.setAvgStar(BigDecimal.valueOf(avg).setScale(1, RoundingMode.HALF_UP).doubleValue());
        return CommonResult.success(vo);
    }

    @Override
    public CommonResult<CommonPage<ProductCommentVO>> listMine(Long memberId, int pageNum, int pageSize) {
        IPage<Comment> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Comment> w = new LambdaQueryWrapper<>();
        w.eq(Comment::getMemberId, memberId);
        w.orderByDesc(Comment::getCreateTime);
        IPage<Comment> result = commentMapper.selectPage(page, w);
        CommonPage<ProductCommentVO> cp = new CommonPage<>();
        cp.setPageNum((int) result.getCurrent());
        cp.setPageSize((int) result.getSize());
        cp.setTotal(result.getTotal());
        cp.setTotalPage((int) ((result.getTotal() + result.getSize() - 1) / result.getSize()));
        cp.setList(result.getRecords().stream().map(this::toVO).collect(Collectors.toList()));
        return CommonResult.success(cp);
    }

    private Long countStar(Long productId, int star) {
        Long n = commentMapper.selectCount(new LambdaQueryWrapper<Comment>()
                .eq(Comment::getProductId, productId)
                .eq(Comment::getStatus, STATUS_APPROVED)
                .eq(Comment::getStar, star));
        return n == null ? 0L : n;
    }

    private ProductCommentVO toVO(Comment c) {
        ProductCommentVO vo = new ProductCommentVO();
        vo.setId(c.getId());
        vo.setStar(c.getStar());
        vo.setContent(c.getContent());
        vo.setPics(c.getPics());
        vo.setAnonymous(c.getAnonymous());
        vo.setNickname(c.getMemberNickname());
        vo.setIcon(c.getMemberIcon());
        vo.setReplyContent(c.getReplyContent());
        vo.setReplyTime(c.getReplyTime());
        vo.setCreateTime(c.getCreateTime());
        return vo;
    }
}
