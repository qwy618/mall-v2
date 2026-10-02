package com.macro.mall.portal.search;

import com.macro.mall.mbg.model.Product;

import java.io.IOException;

public interface EsProductService {
//    void createIndex() throws IOException;
    void deleteIndex() throws IOException;
    void importAll() throws IOException;
    void upsert(Product product) throws IOException;
    void delete(Long id) throws IOException;
    EsSearchResult search(String keyword, Long categoryId, Long brandId,
                          int pageNum, int pageSize) throws IOException;

}
