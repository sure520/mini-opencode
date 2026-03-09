"""FastAPI CRUD 代码生成器

使用 Python 代码直接生成 FastAPI CRUD 代码，而不是使用模板语法。
这样的好处是：
1. 生成器本身是有效的 Python 代码，可以被类型检查和测试
2. 不需要模板引擎，减少依赖
3. 更容易维护和扩展
"""
from typing import Any


def generate_schema(model_name: str, model_name_lower: str) -> str:
    """生成 Pydantic schema 代码
    
    Args:
        model_name: 模型名称（首字母大写，如 Product）
        model_name_lower: 模型名称小写（如 product）
    
    Returns:
        生成的 schema 代码字符串
    """
    return f'''from pydantic import BaseModel
from typing import Optional


class {model_name}Base(BaseModel):
    name: str
    description: Optional[str] = None
    price: float


class {model_name}Create({model_name}Base):
    pass


class {model_name}Update(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None


class {model_name}({model_name}Base):
    id: int
    
    class Config:
        from_attributes = True
'''


def generate_model(model_name: str, model_name_lower: str) -> str:
    """生成 SQLAlchemy 模型代码
    
    Args:
        model_name: 模型名称（首字母大写）
        model_name_lower: 模型名称小写
    
    Returns:
        生成的模型代码字符串
    """
    return f'''from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class {model_name}(Base):
    __tablename__ = "{model_name_lower}"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
'''


def generate_routes(model_name: str, model_name_lower: str) -> str:
    """生成 FastAPI 路由代码
    
    Args:
        model_name: 模型名称（首字母大写）
        model_name_lower: 模型名称小写
    
    Returns:
        生成的路由代码字符串
    """
    return f'''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models.{model_name} import {model_name}
from ..schemas.{model_name} import {model_name} as {model_name}Schema, {model_name}Create, {model_name}Update

router = APIRouter(prefix="/{model_name_lower}", tags=["{model_name_lower}"])


@router.get("", response_model=List[{model_name}Schema])
def get_{model_name_lower}(db: Session = Depends(get_db)):
    return db.query({model_name}).all()


@router.get("/{{id}}", response_model={model_name}Schema)
def get_{model_name_lower}_by_id(id: int, db: Session = Depends(get_db)):
    item = db.query({model_name}).filter({model_name}.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    return item


@router.post("", response_model={model_name}Schema)
def create_{model_name_lower}(item: {model_name}Create, db: Session = Depends(get_db)):
    db_item = {model_name}(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.put("/{{id}}", response_model={model_name}Schema)
def update_{model_name_lower}(id: int, item: {model_name}Update, db: Session = Depends(get_db)):
    db_item = db.query({model_name}).filter({model_name}.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    
    update_data = item.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
    
    db.commit()
    db.refresh(db_item)
    return db_item


@router.delete("/{{id}}")
def delete_{model_name_lower}(id: int, db: Session = Depends(get_db)):
    db_item = db.query({model_name}).filter({model_name}.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    
    db.delete(db_item)
    db.commit()
    return {{"message": f"{model_name} deleted successfully"}}
'''


def generate_readme() -> str:
    """生成 README 文档
    
    Returns:
        生成的 README 内容
    """
    return '''# FastAPI CRUD 模板

## 功能说明

此模板用于快速创建 FastAPI CRUD 接口，包括：
- 基础 CRUD 操作
- 数据库集成
- 数据验证
- 错误处理

## 使用方法

1. 选择此模板
2. 输入模型名称
3. 模板会自动生成完整的 CRUD 接口结构

## 生成的文件

- `schemas/{{model_name}}.py` - Pydantic 数据模型
- `models/{{model_name}}.py` - SQLAlchemy 数据库模型
- `routes/{{model_name}}.py` - FastAPI 路由
- `README.md` - 此文件

## 示例

使用模板生成 Product 模型的代码：
```python
template(runtime, 'fastapi-crud', './src', {'model_name': 'Product', 'ModelName': 'Product'})
```

这将生成：
- `schemas/Product.py`
- `models/Product.py`
- `routes/Product.py`
'''


def generate_all(model_name: str) -> dict[str, str]:
    """生成所有 FastAPI CRUD 文件
    
    Args:
        model_name: 模型名称（如 "Product"）
    
    Returns:
        文件路径到内容的映射字典
    """
    model_name_lower = model_name.lower()
    
    return {
        f"schemas/{model_name}.py": generate_schema(model_name, model_name_lower),
        f"models/{model_name}.py": generate_model(model_name, model_name_lower),
        f"routes/{model_name}.py": generate_routes(model_name, model_name_lower),
        "README.md": generate_readme(),
    }
