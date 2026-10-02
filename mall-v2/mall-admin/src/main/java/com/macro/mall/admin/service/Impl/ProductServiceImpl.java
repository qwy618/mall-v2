package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.dto.ProductParam;
import com.macro.mall.admin.service.ProductService;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.common.mq.ProductMqConstants;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.model.Product;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

@Service
public class ProductServiceImpl implements ProductService {
    @Autowired
    private ProductMapper productMapper;
    @Autowired
    private RabbitTemplate rabbitTemplate;
    @Override
    public CommonResult<CommonPage<Product>> getList(Integer pageNum, Integer pageSize, String keyword, Long brandId, Long categoryId, Integer status) {
        IPage<Product> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Product> w = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(keyword)) {
            // 名称或货号模糊匹配
            w.and(wr -> wr.like(Product::getName, keyword).or().like(Product::getProductSn, keyword));
        }
        if (brandId != null) {
            w.eq(Product::getBrandId, brandId);
        }
        if (categoryId != null) {
            w.eq(Product::getCategoryId, categoryId);
        }
        if (status != null) {
            w.eq(Product::getStatus, status);
        }
        IPage<Product> productIPage = productMapper.selectPage(page, w);
        return CommonResult.success(CommonPage.restPage(productIPage));
    }

    @Override
    public CommonResult<Product> get(Long id) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            return CommonResult.failed("商品不存在");
        }
        return CommonResult.success(product);
    }

    @Override
    public CommonResult<Long> create(ProductParam productParam) {
        Product product = new Product();
        BeanUtils.copyProperties(productParam, product);
        product.setProductSn(genProductSn());
        int insert = productMapper.insert(product);
        rabbitTemplate.convertAndSend(ProductMqConstants.EXCHANGE, ProductMqConstants.KEY, product.getId() + ":CREATE");
        return CommonResult.success(product.getId());
    }

    @Override
    public CommonResult<Long> update(Long id, ProductParam productParam) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            return CommonResult.failed("商品不存在");
        }
        BeanUtils.copyProperties(productParam, product);
        int update = productMapper.updateById(product);
        rabbitTemplate.convertAndSend(ProductMqConstants.EXCHANGE, ProductMqConstants.KEY, id + ":UPDATE");
        return CommonResult.success((long) update);
    }

    @Override
    public CommonResult<Long> delete(Long id) {
        int delete = productMapper.deleteById(id);
        rabbitTemplate.convertAndSend(ProductMqConstants.EXCHANGE, ProductMqConstants.KEY, id + ":DELETE");
        return CommonResult.success((long) delete);
    }

    private String genProductSn() {
        // 时间戳 + 3 位随机，碰撞概率极低
        return "P" + DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS").format(LocalDateTime.now())
                + (int) (Math.random() * 900 + 100);
    }
}
