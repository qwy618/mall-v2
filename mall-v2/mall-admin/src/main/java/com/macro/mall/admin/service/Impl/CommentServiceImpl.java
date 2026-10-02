package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.service.CommentService;
import com.macro.mall.admin.vo.CommentListItemVO;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.CommentMapper;
import com.macro.mall.mbg.model.Comment;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 商品评价后台服务实现。
 */
@Service
public class CommentServiceImpl implements CommentService {

    private static final int STATUS_PENDING = 0;
    private static final int STATUS_APPROVED = 1;
    private static final int STATUS_REJECTED = 2;

    @Autowired
    private CommentMapper commentMapper;

    @Override
    public CommonResult<CommonPage<CommentListItemVO>> list(Integer pageNum, Integer pageSize,
                                                           Long productId, Integer status, String keyword) {
        IPage<Comment> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Comment> w = new LambdaQueryWrapper<>();
        if (productId != null) {
            w.eq(Comment::getProductId, productId);
        }
        if (status != null) {
            w.eq(Comment::getStatus, status);
        }
        if (keyword != null && !keyword.trim().isEmpty()) {
            String kw = keyword.trim();
            w.and(q -> q.like(Comment::getMemberNickname, kw).or().like(Comment::getProductName, kw));
        }
        w.orderByDesc(Comment::getCreateTime);
        IPage<Comment> result = commentMapper.selectPage(page, w);
        CommonPage<CommentListItemVO> cp = new CommonPage<>();
        cp.setPageNum((int) result.getCurrent());
        cp.setPageSize((int) result.getSize());
        cp.setTotal(result.getTotal());
        cp.setTotalPage((int) ((result.getTotal() + result.getSize() - 1) / result.getSize()));
        cp.setList(result.getRecords().stream().map(this::toVO).collect(Collectors.toList()));
        return CommonResult.success(cp);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Void> audit(Long id, Integer status) {
        if (status == null || (status != STATUS_APPROVED && status != STATUS_REJECTED)) {
            return CommonResult.failed("审核状态不合法");
        }
        Comment c = commentMapper.selectById(id);
        if (c == null) return CommonResult.failed("评价不存在");
        if (c.getStatus() == null || c.getStatus() != STATUS_PENDING) {
            return CommonResult.failed("仅待审核的评价可以审核");
        }
        Comment upd = new Comment();
        upd.setId(id);
        upd.setStatus(status);
        commentMapper.updateById(upd);
        return CommonResult.success();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Void> reply(Long id, String replyContent) {
        Comment c = commentMapper.selectById(id);
        if (c == null) return CommonResult.failed("评价不存在");
        if (replyContent == null || replyContent.trim().isEmpty()) {
            return CommonResult.failed("回复内容不能为空");
        }
        Comment upd = new Comment();
        upd.setId(id);
        upd.setReplyContent(replyContent.trim());
        upd.setReplyTime(new Date());
        commentMapper.updateById(upd);
        return CommonResult.success();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public CommonResult<Void> delete(Long id) {
        if (commentMapper.selectById(id) == null) {
            return CommonResult.failed("评价不存在");
        }
        commentMapper.deleteById(id);
        return CommonResult.success();
    }

    private CommentListItemVO toVO(Comment c) {
        CommentListItemVO vo = new CommentListItemVO();
        vo.setId(c.getId());
        vo.setOrderItemId(c.getOrderItemId());
        vo.setOrderId(c.getOrderId());
        vo.setOrderSn(c.getOrderSn());
        vo.setProductId(c.getProductId());
        vo.setProductName(c.getProductName());
        vo.setProductPic(c.getProductPic());
        vo.setMemberId(c.getMemberId());
        vo.setNickname(c.getMemberNickname());
        vo.setIcon(c.getMemberIcon());
        vo.setStar(c.getStar());
        vo.setAnonymous(c.getAnonymous());
        vo.setContent(c.getContent());
        vo.setPics(c.getPics());
        vo.setStatus(c.getStatus());
        vo.setReplyContent(c.getReplyContent());
        vo.setReplyTime(c.getReplyTime());
        vo.setCreateTime(c.getCreateTime());
        return vo;
    }
}
