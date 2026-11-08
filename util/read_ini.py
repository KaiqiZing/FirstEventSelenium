# coding=utf-8
import configparser
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ReadIni(object):
    def __init__(self, file_name):
        """
        :param file_name: INI 文件路径 (必填参数)
        """
        if not file_name:
            raise ValueError("❌ 初始化 ReadIni 失败：必须明确提供 file_name (文件路径)！")

        # 处理相对路径转绝对路径
        if file_name.startswith("../"):
            self.file_name = os.path.join(BASE_DIR, file_name.replace("../", ""))
        else:
            self.file_name = file_name

        self.cf = self.load_ini()

    def load_ini(self):
        """加载ini文件"""
        cf = configparser.ConfigParser()

        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"❌ 配置文件不存在，请检查路径: {self.file_name}")

        try:
            cf.read(self.file_name, encoding="utf-8")
            return cf
        except Exception as e:
            raise RuntimeError(f"❌ 配置文件解析失败: {self.file_name}, Error: {e}")

    def get_value(self, key, node):
        """
        获取具体的value
        :param key: 元素的键名 (必填)
        :param node: INI文件中的节点/Section名 (必填)
        """
        if not node:
            raise ValueError(f"❌ 读取配置失败：必须指定 node (节点名称)！当前请求的 key 为: {key}")
        if not key:
            raise ValueError(f"❌ 读取配置失败：必须指定 key (元素名称)！当前请求的 node 为: {node}")

        try:
            return self.cf.get(node, key)
        except configparser.NoSectionError:
            raise ValueError(f"❌ 错误: 未找到节点 [{node}] (所在文件: {self.file_name})")
        except configparser.NoOptionError:
            raise ValueError(f"❌ 错误: 节点 [{node}] 下未找到 key [{key}] (所在文件: {self.file_name})")


if __name__ == "__main__":
    ini_reader = ReadIni(file_name="../config/InteractElement.ini")
    print(ini_reader.get_value(key="I01_Operator", node="I01"))
