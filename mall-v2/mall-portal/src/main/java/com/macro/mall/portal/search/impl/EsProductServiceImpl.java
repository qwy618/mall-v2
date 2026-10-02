package com.macro.mall.portal.search.impl;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch._types.query_dsl.BoolQuery;
import co.elastic.clients.elasticsearch._types.query_dsl.MultiMatchQuery;
import co.elastic.clients.elasticsearch.core.BulkRequest;
import co.elastic.clients.elasticsearch.core.BulkResponse;
import co.elastic.clients.elasticsearch.core.SearchRequest;
import co.elastic.clients.elasticsearch.core.SearchResponse;
import co.elastic.clients.elasticsearch.core.bulk.BulkResponseItem;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.mbg.mapper.ProductMapper;
import com.macro.mall.mbg.model.Product;
import com.macro.mall.mbg.model.ProductDocument;
import com.macro.mall.portal.search.EsProductService;
import com.macro.mall.portal.search.EsSearchResult;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.List;
import java.util.stream.Collectors;

import static com.macro.mall.mbg.model.ProductDocument.convert;


@Service
@Slf4j
public class EsProductServiceImpl implements EsProductService {

    @Autowired
    private ElasticsearchClient client;
    @Autowired
    private ProductMapper productMapper;
//    @Override
//    public void createIndex() throws IOException {
//
//    }

    @Override
    public void deleteIndex() throws IOException {
        client.indices().delete(d -> d.index("product"));
    }

    @Override
    public void importAll() throws IOException {
        List<Product> list = productMapper.selectList(new LambdaQueryWrapper<Product>());
        BulkRequest.Builder br = new BulkRequest.Builder();
        for (Product p : list) {
            ProductDocument doc = convert(p);
            br.operations(op -> op.index(idx -> idx
                    .index("product")
                    .id(String.valueOf(doc.getId()))   // _id = 商品 id
                    .document(doc)));
        }
        BulkResponse resp = client.bulk(br.build());
        if (resp.errors()) {
            for (BulkResponseItem item : resp.items()) {
                if (item.error() != null) {
                    log.error("ES 导入失败 id={} : {}", item.id(), item.error().reason());
                }
            }
        }
    }

    @Override
    public void upsert(Product product) throws IOException {
        client.index(i -> i
                .index("product")
                .id(String.valueOf(product.getId()))
                .document(convert(product)));
    }

    @Override
    public void delete(Long id) throws IOException {
        client.delete(d -> d.index("product").id(String.valueOf(id)));
    }

    @Override
    public EsSearchResult search(String keyword, Long categoryId, Long brandId, int pageNum, int pageSize) throws IOException {
        BoolQuery.Builder bq = new BoolQuery.Builder();
        bq.must(m -> m.multiMatch(MultiMatchQuery.of(mm -> mm
                .query(keyword)
                .fields(List.of("name", "subTitle"))
                .analyzer("ik_smart"))));
        if (categoryId != null) {
            bq.filter(f -> f.term(t -> t.field("categoryId").value(categoryId)));
        }
        if (brandId != null) {
            bq.filter(f -> f.term(t -> t.field("brandId").value(brandId)));
        }
        bq.filter(f -> f.term(t -> t.field("status").value(1))); // 只搜上架商品

        SearchResponse<ProductDocument> resp = client.search(SearchRequest.of(s -> s
                        .index("product")
                        .query(bq.build()._toQuery())
                        .from((pageNum - 1) * pageSize)
                        .size(pageSize)
                        .trackTotalHits(t -> t.enabled(true))),
                ProductDocument.class);

        List<Long> ids = resp.hits().hits().stream()
                .map(h -> Long.valueOf(h.id()))
                .collect(Collectors.toList());
        long total = resp.hits().total() != null ? resp.hits().total().value() : 0L;
        return new EsSearchResult(ids, total);
    }
}
