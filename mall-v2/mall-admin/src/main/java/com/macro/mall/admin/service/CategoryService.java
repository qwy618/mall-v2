package com.macro.mall.admin.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.macro.mall.admin.dto.CategoryParam;
import com.macro.mall.mbg.model.Category;
import jakarta.validation.Valid;

public interface CategoryService {
    IPage<Category> list(Integer pageNum, Integer pageSize,Integer parentId);

    Category getItem(Long id);

    Long create(CategoryParam categoryParam);

    Long update(Long id, @Valid CategoryParam categoryParam);

    Long delete(Long id);
}
