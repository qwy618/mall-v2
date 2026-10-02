package com.macro.mall.portal.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.mapper.CategoryMapper;
import com.macro.mall.mbg.model.Category;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/category")
public class CategoryController {

    @Autowired
    private CategoryMapper categoryMapper;

    /** 分类树：按 sort 升序，组装成 顶级 -> 子级 两级结构 */
    @GetMapping("/list")
    public CommonResult<List<CategoryNode>> list() {
        List<Category> all = categoryMapper.selectList(
                new LambdaQueryWrapper<Category>().orderByAsc(Category::getSort));

        Map<Long, CategoryNode> nodeMap = new LinkedHashMap<>();
        for (Category c : all) {
            CategoryNode node = new CategoryNode();
            node.setId(c.getId());
            node.setName(c.getName());
            node.setIcon(c.getIcon());
            node.setParentId(c.getParentId());
            node.setChildren(new ArrayList<>());
            nodeMap.put(c.getId(), node);
        }

        List<CategoryNode> roots = new ArrayList<>();
        for (CategoryNode node : nodeMap.values()) {
            Long pid = node.getParentId();
            if (pid == null || pid == 0) {
                roots.add(node);
            } else {
                CategoryNode parent = nodeMap.get(pid);
                if (parent != null) {
                    parent.getChildren().add(node);
                } else {
                    roots.add(node); // 父级缺失时兜底挂到顶级
                }
            }
        }
        return CommonResult.success(roots);
    }

    @lombok.Data
    public static class CategoryNode {
        private Long id;
        private String name;
        private String icon;
        private Long parentId;
        private List<CategoryNode> children;
    }
}
