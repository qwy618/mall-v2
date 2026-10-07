package com.macro.mall.portal.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.mapper.SkuMapper;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.mbg.model.Sku;
import com.macro.mall.portal.dao.ProductListParam;
import com.macro.mall.portal.search.EsProductService;
import com.macro.mall.portal.search.EsSearchResult;
import com.macro.mall.portal.vo.ProductDetailVO;
import com.macro.mall.portal.vo.ProductVO;
import com.macro.mall.service.ProductAttributeService;
import com.macro.mall.service.vo.SpecFacetVO;
import com.macro.mall.service.vo.SpecMatchVO;
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
     * 商品列表：分页 + 关键词搜索 + 分类/品牌/规格筛选，按 id 倒序，附 SKU 最低价。
     *
     * <p>两条路径：有 keyword → ES；否则 → DB（分类/品牌浏览 + 规格筛选）。
     */
    @GetMapping("/list")
    public CommonResult<CommonPage<ProductVO>> list(ProductListParam param) {

        // ===== 有搜索词 → 走 ES =====
        if (param.getKeyword() != null && !param.getKeyword().isBlank()) {
            try {
                EsSearchResult r = esProductService.search(param.getKeyword(), param.getCategoryId(),
                        param.getBrandId(), param.getPageNum(), param.getPageSize());
                if (r.getIds().isEmpty()) {
                    // ⚠️ 空集直接返空页，绝不传 selectBatchIds
                    return CommonResult.success(emptyProductPage(param.getPageNum(), param.getPageSize()));
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
                Page<ProductVO> voPage = new Page<>(param.getPageNum(), param.getPageSize(), r.getTotal());
                voPage.setRecords(vos);
                return CommonResult.success(CommonPage.restPage(voPage));
            } catch (Exception e) {
                // ES 挂了降级到 DB 关键词查询，保证可用
                log.warn("ES 搜索失败，降级 DB，kw={}", param.getKeyword(), e);
            }
        }

        // ===== 无搜索词 或 ES 异常 → DB 逻辑（分类/品牌浏览 + 规格筛选）=====
        Map<String, List<String>> specs = param.parseSpecs();

        // 决策④ 边界：规格筛选只在「无 keyword」的 DB 路径生效 —— ES 文档里没有规格字段，
        // 硬要做就得改索引结构。同时传 keyword 与 attrs 时忽略 attrs 并告警，另记债务（设计文档 §8.3）。
        if (!specs.isEmpty() && param.getKeyword() != null && !param.getKeyword().isBlank()) {
            log.warn("keyword 与 attrs 同时传入：ES 分支不支持规格筛选，本次忽略 attrs。kw={}", param.getKeyword());
            specs = Collections.emptyMap();
        }

        // 规格筛选（P2）：先反查命中商品 + 命中 SKU 的最低价，再把商品 id 作为 in 条件交给常规分页。
        // 之所以不自己拼 Page：并回常规分页后，total 天然就是
        // 「再叠加分类/品牌/上架过滤之后的 DISTINCT 商品数」，省掉一个最容易算错的环节。
        Map<Long, BigDecimal> specMinPrice = Collections.emptyMap();
        if (!specs.isEmpty()) {
            SpecMatchVO match = productAttributeService.matchProductsBySpecs(param.getCategoryId(), specs);
            if (match.getProductIds().isEmpty()) {
                // ⚠️ 空集必须直接返空页：绝不让 in() 收到空集合（会拼出 IN () 直接语法错），
                //    与上面 ES 分支、以及历史上 selectBatchIds(空) 是同一个坑。
                return CommonResult.success(emptyProductPage(param.getPageNum(), param.getPageSize()));
            }
            specMinPrice = match.getMinPriceByProduct();
        }

        Page<Product> page = new Page<>(param.getPageNum(), param.getPageSize());
        LambdaQueryWrapper<Product> w = new LambdaQueryWrapper<>();
        if (param.getKeyword() != null && !param.getKeyword().isBlank()) {
            w.like(Product::getName, param.getKeyword());
        }
        if (param.getCategoryId() != null) w.eq(Product::getCategoryId, param.getCategoryId());
        if (param.getBrandId() != null) w.eq(Product::getBrandId, param.getBrandId());
        // 🔴 补上架过滤：这条路径原先不滤 status，status=0 的下架商品会混进 C 端列表
        //    （P2 验收 #5；/product/similar 一直是滤的，这里属于漏网）。
        w.eq(Product::getStatus, 1);
        if (!specMinPrice.isEmpty()) {
            w.in(Product::getId, specMinPrice.keySet());
        }
        w.orderByDesc(Product::getId);
        productMapper.selectPage(page, w);

        // 展示价：走规格筛选时用「命中规格那批 SKU」的最低价，否则用商品全局最低价（验收 #8）
        Map<Long, BigDecimal> minPriceMap = specMinPrice.isEmpty()
                ? loadMinPrices(page.getRecords())
                : specMinPrice;
        List<ProductVO> vos = page.getRecords().stream()
                .map(p -> ProductVO.from(p, minPriceMap.get(p.getId())))
                .collect(Collectors.toList());
        Page<ProductVO> voPage = new Page<>(page.getCurrent(), page.getSize(), page.getTotal());
        voPage.setRecords(vos);
        return CommonResult.success(CommonPage.restPage(voPage));
    }

    /**
     * 筛选面板数据源（P2）：某分类下「规格属性 → 可选值 → 命中（已上架）商品数」。
     * 免登录（`/product/**` 已在 SecurityConfig 白名单）；无分类 / 无规格数据时返回 []，
     * 前端据此整块隐藏面板 —— 筛选是增强，不该拖垮原有浏览。
     */
    @GetMapping("/spec-filters")
    public CommonResult<List<SpecFacetVO>> specFilters(@RequestParam(required = false) Long categoryId) {
        return CommonResult.success(productAttributeService.listSpecFacets(categoryId));
    }

    /** 空结果分页（total = 0、list = []）。抽出来给「反查无命中」与「ES 无命中」两处共用 */
    private CommonPage<ProductVO> emptyProductPage(Integer pageNum, Integer pageSize) {
        Page<ProductVO> empty = new Page<>(pageNum, pageSize, 0);
        empty.setRecords(Collections.emptyList());
        return CommonPage.restPage(empty);
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
