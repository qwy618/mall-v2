package com.macro.mall.portal.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.MemberProductCollectionMapper;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.MemberProductCollection;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.mbg.model.Sku;
import com.macro.mall.portal.service.CollectService;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

@Service
public class CollectServiceImpl implements CollectService {

    private final MemberProductCollectionMapper collectionMapper;
    private final ProductMapper productMapper;
    private final SkuMapper skuMapper;

    public CollectServiceImpl(MemberProductCollectionMapper collectionMapper,
                             ProductMapper productMapper,
                             SkuMapper skuMapper) {
        this.collectionMapper = collectionMapper;
        this.productMapper = productMapper;
        this.skuMapper = skuMapper;
    }

    @Override
    public void add(Long memberId, Long productId) {
        long exists = collectionMapper.selectCount(new LambdaQueryWrapper<MemberProductCollection>()
                .eq(MemberProductCollection::getMemberId, memberId)
                .eq(MemberProductCollection::getProductId, productId));
        if (exists > 0) {
            return; // 幂等：已收藏则忽略
        }
        Product product = productMapper.selectById(productId);
        if (product == null) {
            throw new BusinessException("商品不存在");
        }
        // 计算 SKU 最低价（与商品详情一致）
        List<Sku> skus = skuMapper.selectList(new LambdaQueryWrapper<Sku>()
                .eq(Sku::getProductId, productId));
        BigDecimal lowest = skus.stream()
                .map(Sku::getPrice)
                .filter(Objects::nonNull)
                .min(Comparator.naturalOrder())
                .orElse(BigDecimal.ZERO);

        MemberProductCollection c = new MemberProductCollection();
        c.setMemberId(memberId);
        c.setProductId(productId);
        c.setProductName(product.getName());
        c.setProductPic(product.getPic());
        c.setProductPrice(lowest);
        c.setCreateTime(LocalDateTime.now());
        collectionMapper.insert(c);
    }

    @Override
    public void delete(Long memberId, Long productId) {
        collectionMapper.delete(new LambdaQueryWrapper<MemberProductCollection>()
                .eq(MemberProductCollection::getMemberId, memberId)
                .eq(MemberProductCollection::getProductId, productId));
    }

    @Override
    public List<MemberProductCollection> list(Long memberId) {
        return collectionMapper.selectList(new LambdaQueryWrapper<MemberProductCollection>()
                .eq(MemberProductCollection::getMemberId, memberId)
                .orderByDesc(MemberProductCollection::getCreateTime));
    }

    @Override
    public boolean isCollected(Long memberId, Long productId) {
        return collectionMapper.selectCount(new LambdaQueryWrapper<MemberProductCollection>()
                .eq(MemberProductCollection::getMemberId, memberId)
                .eq(MemberProductCollection::getProductId, productId)) > 0;
    }
}
