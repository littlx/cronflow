from app.registry.decorator import register_task, TASKS
from app.registry.introspect import introspect_parameters


def test_parameter_introspection():
    """测试参数自省描述提取，同时兼容带类型与不带类型的 Sphinx/Google :param 格式。"""
    
    # 1. 注册无类型描述的任务
    @register_task(name="Introspect No Types")
    def task_no_types(path: str, count: int = 10):
        """
        :param path: 保存文件的物理路径
        :param count: 循环计数值
        """
        pass

    # 2. 注册带类型描述的任务
    @register_task(name="Introspect With Types")
    def task_with_types(url: str, timeout: float = 3.5):
        """
        :param str url: 请求的目标链接地址
        :param float timeout: 连接超时阈值
        """
        pass

    # 验证任务 1 描述是否全部正确提取
    t1 = TASKS.get("tasks.test_registry.task_no_types")
    assert t1 is not None
    params1 = t1["parameters"]
    assert len(params1) == 2
    assert params1[0]["name"] == "path"
    assert params1[0]["description"] == "保存文件的物理路径"
    assert params1[1]["name"] == "count"
    assert params1[1]["description"] == "循环计数值"

    # 验证任务 2 描述是否全部正确提取
    t2 = TASKS.get("tasks.test_registry.task_with_types")
    assert t2 is not None
    params2 = t2["parameters"]
    assert len(params2) == 2
    assert params2[0]["name"] == "url"
    assert params2[0]["description"] == "请求的目标链接地址"
    assert params2[1]["name"] == "timeout"
    assert params2[1]["description"] == "连接超时阈值"
