package com.macro.mall.portal.service;

import com.macro.mall.mbg.model.MemberProductCollection;

import java.util.List;

public interface CollectService {
    /** 收藏商品（幂等：已收藏则忽略）；快照商品名/图/最低价 */
    void add(Long memberId, Long productId);

    /** 取消收藏（按 会员+商品 删除） */
    void delete(Long memberId, Long productId);

    /** 当前会员的收藏列表（按收藏时间倒序） */
    List<MemberProductCollection> list(Long memberId);

    /** 是否已收藏某商品 */
    boolean isCollected(Long memberId, Long productId);
}
