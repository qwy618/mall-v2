package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.dto.AttributeParam;
import com.macro.mall.admin.service.AttributeService;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.ProductAttributeMapper;
import com.macro.mall.mbg.mapper.ProductAttributeValueMapper;
import com.macro.mall.mbg.mapper.SkuAttributeValueMapper;
import com.macro.mall.mbg.model.ProductAttribute;
import com.macro.mall.mbg.model.ProductAttributeValue;
import com.macro.mall.mbg.model.SkuAttributeValue;
import com.macro.mall.service.ProductAttributeService;
import com.macro.mall.service.vo.AttributeItemVO;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 属性定义管理实现。
 *
 * 与 mall-service 的 ProductAttributeService 分工：
 *   · 定义（product_attribute）的 CRUD 在管理端，因为只有运营会改；
 *   · 取值（参数/规格）的读写在 mall-service，因为 admin 与 portal 都要用。
 */
@Service
public class AttributeServiceImpl implements AttributeService {

    @Autowired
    private ProductAttributeMapper productAttributeMapper;
    @Autowired
    private ProductAttributeValueMapper productAttributeValueMapper;
    @Autowired
    private SkuAttributeValueMapper skuAttributeValueMapper;
    /** 跨端属性能力（mall-service），不重复实现取值读写 */
    @Autowired
    private ProductAttributeService productAttributeService;

    @Override
    public IPage<ProductAttribute> list(Long categoryId, Integer type, Integer pageNum, Integer pageSize) {
        Page<ProductAttribute> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<ProductAttribute> w = new LambdaQueryWrapper<>();
        if (categoryId != null) {
            w.eq(ProductAttribute::getCategoryId, categoryId);
        }
        if (type != null) {
            w.eq(ProductAttribute::getType, type);
        }
        w.orderByAsc(ProductAttribute::getCategoryId)
                .orderByAsc(ProductAttribute::getSort)
                .orderByAsc(ProductAttribute::getId);
        return productAttributeMapper.selectPage(page, w);
    }

    @Override
    public List<ProductAttribute> listByProduct(Long productId, Integer type) {
        return productAttributeService.listDefinitionsByProduct(productId, type);
    }

    @Override
    public ProductAttribute getItem(Long id) {
        return productAttributeMapper.selectById(id);
    }

    @Override
    public Long create(AttributeParam param) {
        checkType(param.getType());
        if (exists(param.getCategoryId(), param.getName(), null)) {
            // 表上有 uk_category_name，但直接撞唯一键只会得到一句"系统繁忙"，
            // 所以先查一次给出可读的提示（并发下仍由唯一键兜底）
            throw new BusinessException("该分类下已存在属性「" + param.getName() + "」");
        }
        ProductAttribute entity = new ProductAttribute();
        BeanUtils.copyProperties(param, entity);
        if (entity.getInputType() == null) {
            entity.setInputType(defaultInputType(param.getType()));
        }
        if (entity.getSort() == null) {
            entity.setSort(0);
        }
        productAttributeMapper.insert(entity);
        return entity.getId();
    }

    @Override
    public Long update(Long id, AttributeParam param) {
        checkType(param.getType());
        ProductAttribute exist = productAttributeMapper.selectById(id);
        if (exist == null) {
            throw new BusinessException("属性不存在");
        }
        if (exists(param.getCategoryId(), param.getName(), id)) {
            throw new BusinessException("该分类下已存在属性「" + param.getName() + "」");
        }
        // 已经产生取值后再改「归属分类」或「规格/参数类型」，会让已写入的行指向错误的池子
        boolean scopeChanged = !exist.getCategoryId().equals(param.getCategoryId())
                || !exist.getType().equals(param.getType());
        if (scopeChanged && hasValues(id, exist.getType())) {
            throw new BusinessException("该属性已被商品取值，不能改所属分类或属性类型；请先清理取值");
        }
        ProductAttribute entity = new ProductAttribute();
        BeanUtils.copyProperties(param, entity);
        entity.setId(id);
        if (entity.getInputType() == null) {
            entity.setInputType(exist.getInputType());
        }
        if (entity.getSort() == null) {
            entity.setSort(exist.getSort());
        }
        return (long) productAttributeMapper.updateById(entity);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long delete(Long id) {
        ProductAttribute exist = productAttributeMapper.selectById(id);
        if (exist == null) {
            throw new BusinessException("属性不存在");
        }
        // 拒绝删除而不是级联清值：静默丢掉商品的参数/规格是不可逆的，
        // 让运营显式先清理，避免"删个属性顺手把商品规格删了"
        if (hasValues(id, exist.getType())) {
            throw new BusinessException("该属性已被商品取值使用，请先清理取值再删除");
        }
        return (long) productAttributeMapper.deleteById(id);
    }

    @Override
    public List<AttributeItemVO> getProductParams(Long productId) {
        return productAttributeService.listProductParams(productId);
    }

    @Override
    public void saveProductParams(Long productId, List<AttributeItemVO> items) {
        productAttributeService.saveProductParams(productId, items);
    }

    // ==================== 内部工具 ====================

    private void checkType(Integer type) {
        if (type == null || (type != ProductAttribute.TYPE_SPEC && type != ProductAttribute.TYPE_PARAM)) {
            throw new BusinessException("属性类型只能是 0(规格) 或 1(参数)");
        }
    }

    private int defaultInputType(Integer type) {
        // 规格天然是「从候选值里选一个」；参数（屏幕尺寸/上市年份）通常得手打
        return ProductAttribute.TYPE_SPEC == type ? 1 : 0;
    }

    private boolean exists(Long categoryId, String name, Long excludeId) {
        LambdaQueryWrapper<ProductAttribute> w = new LambdaQueryWrapper<>();
        w.eq(ProductAttribute::getCategoryId, categoryId)
                .eq(ProductAttribute::getName, name);
        if (excludeId != null) {
            w.ne(ProductAttribute::getId, excludeId);
        }
        return productAttributeMapper.selectCount(w) > 0L;
    }

    /** 该属性在对应的值表里是否已有数据（规格查 sku_attribute_value，参数查 product_attribute_value） */
    private boolean hasValues(Long attributeId, Integer type) {
        if (Integer.valueOf(ProductAttribute.TYPE_SPEC).equals(type)) {
            return skuAttributeValueMapper.selectCount(
                    new LambdaQueryWrapper<SkuAttributeValue>()
                            .eq(SkuAttributeValue::getAttributeId, attributeId)) > 0L;
        }
        return productAttributeValueMapper.selectCount(
                new LambdaQueryWrapper<ProductAttributeValue>()
                        .eq(ProductAttributeValue::getAttributeId, attributeId)) > 0L;
    }
}
