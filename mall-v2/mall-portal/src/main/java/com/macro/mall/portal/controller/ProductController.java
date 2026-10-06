package com.macro.mall.portal.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.mbg.model.Sku;
import com.macro.mall.portal.search.EsProductService;
import com.macro.mall.portal.search.EsSearchResult;
import com.macro.mall.portal.vo.ProductDetailVO;
import com.macro.mall.portal.vo.ProductVO;
import com.macro.mall.service.ProductAttributeService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/product")
@Slf4j
public class ProductController {

    @Autowired
    private ProductMapper productMapper;
    @Autowired
    private EsProductService esProductService;

    @Autowired
    private SkuMapper skuMapper;

    /**
     * 跨端属性能力（mall-service，债务1）：商品参数 + 规格选项。
     * C 端只读——规格值由管理端保存 SKU 时从 sp_data 同步过来。
     */
    @Autowired
    private ProductAttributeService productAttributeService;

    /**
     * 商品列表：分页 + 关键词（按名称）筛选，按 id 倒序，附 SKU 最低价
     */
    @GetMapping("/list")
    public CommonResult<CommonPage<ProductVO>> list(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) Long brandId,
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize) {

        // ===== 有搜索词 → 走 ES =====
        if (keyword != null && !keyword.isBlank()) {
            try {
                EsSearchResult r = esProductService.search(keyword, categoryId, brandId, pageNum, pageSize);
                if (r.getIds().isEmpty()) {
                    // ⚠️ 空集直接返空页，绝不传 selectBatchIds
                    Page<ProductVO> empty = new Page<>(pageNum, pageSize, 0);
                    empty.setRecords(Collections.emptyList());
                    return CommonResult.success(CommonPage.restPage(empty));
                }
                List<Product> products = productMapper.selectBatchIds(r.getIds());
                // ⚠️ selectBatchIds 顺序 ≠ ES 相关度顺序，必须手动按 r.ids 重排
                Map<Long, Product> map = products.stream()
                        .collect(Collectors.toMap(Product::getId, p -> p));
                List<Product> ordered = r.getIds().stream()
                        .map(map::get)
                        .filter(Objects::nonNull)
                        .collect(Collectors.toList());
                Map<Long, BigDecimal> minPriceMap = loadMinPrices(ordered);
                List<ProductVO> vos = ordered.stream()
                        .map(p -> ProductVO.from(p, minPriceMap.get(p.getId())))
                        .collect(Collectors.toList());
                Page<ProductVO> voPage = new Page<>(pageNum, pageSize, r.getTotal());
                voPage.setRecords(vos);
                return CommonResult.success(CommonPage.restPage(voPage));
            } catch (Exception e) {
                // ES 挂了降级到 DB 关键词查询，保证可用
                log.warn("ES 搜索失败，降级 DB，kw={}", keyword, e);
            }
        }

        // ===== 无搜索词 或 ES 异常 → 原 DB 逻辑（分类/品牌浏览）=====
        Page<Product> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Product> w = new LambdaQueryWrapper<>();
        if (keyword != null && !keyword.isBlank()) {
            w.like(Product::getName, keyword);
        }
        if (categoryId != null) w.eq(Product::getCategoryId, categoryId);
        if (brandId != null) w.eq(Product::getBrandId, brandId);
        w.orderByDesc(Product::getId);
        productMapper.selectPage(page, w);

        Map<Long, BigDecimal> minPriceMap = loadMinPrices(page.getRecords());
        List<ProductVO> vos = page.getRecords().stream()
                .map(p -> ProductVO.from(p, minPriceMap.get(p.getId())))
                .collect(Collectors.toList());
        Page<ProductVO> voPage = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        voPage.setRecords(vos);
        return CommonResult.success(CommonPage.restPage(voPage));
    }

//    /** 手动重灌索引（调试用） */
//    @PostMapping("/search/reindex")
//    public CommonResult<String> reindex() {
//        try {
//            esProductService.deleteIndex();
//            esProductService.createIndex();
//            esProductService.importAll();
//            return CommonResult.success("reindex done");
//        } catch (Exception e) {
//            return CommonResult.failed(e.getMessage());



    /** 商品详情：含 SKU 列表与 SKU 最低价 */
    @GetMapping("/{id}")
    public CommonResult<ProductDetailVO> detail(@PathVariable Long id) {
        Product product = productMapper.selectById(id);
        if (product == null) {
            return CommonResult.failed("商品不存在");
        }
        List<Sku> skus = skuMapper.selectList(
                new LambdaQueryWrapper<Sku>().eq(Sku::getProductId, id));
        BigDecimal lowestPrice = skus.stream()
                .map(Sku::getPrice)
                .filter(Objects::nonNull)
                .min(Comparator.naturalOrder())
                .orElse(null);
        ProductDetailVO vo = new ProductDetailVO();
        vo.setProduct(ProductVO.from(product, lowestPrice));
        vo.setSkus(skus);
        // 债务1：商品参数（type=1，仅展示）与规格选项（type=0，按属性名分组的可选值）。
        // 都是空列表兜底，前端按"有数据才渲染"处理，老商品不会因为没配属性而报错。
        vo.setAttributes(productAttributeService.listProductParams(id));
        vo.setSpecOptions(productAttributeService.listSpecOptions(id));
        return CommonResult.success(vo);
    }

    /**
     * 相关推荐（猜你喜欢-详情页版）：同分类、上架、排除自身，按销量倒序取前 N。
     * 免登录；若同分类商品不足，前端可结合品牌维度二次召回（后续扩展）。
     */
    @GetMapping("/similar/{id}")
    public CommonResult<List<ProductVO>> similar(
            @PathVariable Long id,
            @RequestParam(defaultValue = "8") Integer pageSize) {
        Product cur = productMapper.selectById(id);
        if (cur == null) {
            return CommonResult.success(Collections.emptyList());
        }
        int limit = Math.min(pageSize == null ? 8 : pageSize, 20);
        LambdaQueryWrapper<Product> w = new LambdaQueryWrapper<>();
        w.eq(Product::getStatus, 1);
        if (cur.getCategoryId() != null) {
            w.eq(Product::getCategoryId, cur.getCategoryId());
        }
        w.ne(Product::getId, id);
        w.orderByDesc(Product::getSale);
        w.last("LIMIT " + limit);
        List<Product> similars = productMapper.selectList(w);
        Map<Long, BigDecimal> minPriceMap = loadMinPrices(similars);
        List<ProductVO> vos = similars.stream()
                .map(p -> ProductVO.from(p, minPriceMap.get(p.getId())))
                .collect(Collectors.toList());
        return CommonResult.success(vos);
    }

    /** 一次性查出给定商品的 SKU 最低价，返回 productId -> minPrice */
    private Map<Long, BigDecimal> loadMinPrices(List<Product> products) {
        Map<Long, BigDecimal> map = new HashMap<>();
        if (products == null || products.isEmpty()) {
            return map;
        }
        List<Long> ids = products.stream().map(Product::getId).toList();
        List<Sku> skus = skuMapper.selectList(
                new LambdaQueryWrapper<Sku>().in(Sku::getProductId, ids));
        for (Sku s : skus) {
            if (s.getPrice() == null) {
                continue;
            }
            map.merge(s.getProductId(), s.getPrice(), BigDecimal::min);
        }
        return map;
    }
}
