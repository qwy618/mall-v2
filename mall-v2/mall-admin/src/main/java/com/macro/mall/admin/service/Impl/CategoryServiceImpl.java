package com.macro.mall.admin.service.Impl;

import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.macro.mall.admin.dto.CategoryParam;
import com.macro.mall.admin.service.CategoryService;
import com.macro.mall.common.ResultCode;
import com.macro.mall.common.exception.BusinessException;
import com.macro.mall.mbg.mapper.CategoryMapper;
import com.macro.mall.mbg.model.Category;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class CategoryServiceImpl implements CategoryService {
    @Autowired
    private CategoryMapper categoryMapper;
    @Override
    public IPage<Category> list(Integer pageNum, Integer pageSize,Integer parentId) {
        //1.创建一个page对象
        Page<Category> page = new Page<>(pageNum, pageSize);
        //2.导入mapper
        LambdaQueryWrapper<Category> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(parentId != null,Category::getParentId, parentId);
        return categoryMapper.selectPage(page, wrapper);
    }

    @Override
    public Category getItem(Long id) {
        Category category = categoryMapper.selectById(id);
        if(category == null){
            throw new BusinessException(ResultCode.NOT_FOUND,"分类不存在");
        }
        return category;
    }

    @Override
    public Long create(CategoryParam categoryParam) {
        Category category = new Category();
        BeanUtils.copyProperties(categoryParam, category);
        int insert = categoryMapper.insert(category);
        return category.getId();
    }

    @Override
    public Long update(Long id, CategoryParam categoryParam) {
        Category category = new Category();
        BeanUtils.copyProperties(categoryParam, category);
        category.setId(id);
        int update = categoryMapper.updateById(category);
        return (long) update;
    }

    @Override
    public Long delete(Long id) {
        int rows = categoryMapper.deleteById(id);
        return (long) rows;
    }

}
