"""模板工具

提供代码模板生成功能，支持多种模板类型：
- python-api: Python API 模板
- react-component: React 组件模板
- fastapi-crud: FastAPI CRUD 完整示例

使用代码生成器而不是模板字符串，确保生成的代码质量。
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any

from langchain.tools import ToolRuntime, tool


@tool("template")
def template(
    runtime: ToolRuntime,
    template_name: str,
    target_dir: str,
    variables: Optional[Dict[str, Any]] = None,
) -> str:
    """使用模板生成代码
    
    Args:
        template_name: 模板名称 (python-api, react-component, fastapi-crud)
        target_dir: 目标目录
        variables: 模板变量字典
    
    Returns:
        生成结果的描述
    """
    target_path = Path(target_dir)
    if not target_path.exists():
        target_path.mkdir(parents=True, exist_ok=True)
    
    # 根据模板名称选择不同的生成器
    if template_name == "fastapi-crud":
        from mini_opencode.tools.template.fastapi_crud_generator import generate_all
        
        # 获取模型名称
        model_name = variables.get("ModelName", "Item") if variables else "Item"
        
        # 生成所有文件
        files = generate_all(model_name)
        
        # 写入文件
        generated_files = []
        for file_path, content in files.items():
            full_path = target_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            generated_files.append(str(full_path))
        
        return f"成功使用模板 {template_name} 生成代码到 {target_dir}\n生成的文件：\n" + "\n".join(generated_files)
    
    # 其他模板类型暂时使用旧的模板目录方式
    template_dir = Path("skills") / "templates" / template_name
    
    if not template_dir.exists():
        return f"错误：模板 {template_name} 不存在"
    
    # 默认变量
    default_variables: Dict[str, Any] = {
        "project_name": "my-project",
        "author_name": "Developer",
        "author_email": "developer@example.com",
        "ComponentName": "MyComponent",
        "component-name": "my-component",
        "model_name": "Item",
        "ModelName": "Item",
    }
    
    # 合并用户变量
    if variables:
        default_variables.update(variables)
    
    # 自动生成 model_name_lower 变量
    if "model_name" in default_variables:
        default_variables["model_name_lower"] = default_variables["model_name"].lower()
    
    # 复制并处理模板文件
    generated_files = []
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            template_file = Path(root) / file
            # 计算相对路径
            relative_path = template_file.relative_to(template_dir)
            # 处理文件名中的模板变量
            relative_path_str = str(relative_path)
            for key, value in default_variables.items():
                relative_path_str = relative_path_str.replace(f"{{{{{key}}}}}", str(value))
            # 处理模板变量
            target_file_path = target_path / relative_path_str
            
            # 创建目标目录
            target_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 读取模板内容
            with open(template_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 替换变量
            for key, value in default_variables.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            
            # 写入目标文件
            with open(target_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            generated_files.append(str(target_file_path))
    
    return f"成功使用模板 {template_name} 生成代码到 {target_dir}\n生成的文件：\n" + "\n".join(generated_files)
