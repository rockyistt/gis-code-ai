#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step Level Data 分析 - 转化为 DataFrame
"""

import json
import pandas as pd
from pathlib import Path

# ========== 加载数据 ==========
data_file = Path(r"C:\Luqi's internship\Github\gis-code-ai\data\processed\step_level_data.jsonl")

print("=" * 80)
print("📂 加载 step_level_data.jsonl...")
print("=" * 80)

# 读取 JSONL 文件
data_list = []
with open(data_file, 'r', encoding='utf-8') as f:
    for line_num, line in enumerate(f, 1):
        try:
            data_list.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"⚠️  第 {line_num} 行解析失败: {e}")

print(f"\n✅ 加载完成: {len(data_list)} 条记录")

# ========== 转化为 DataFrame ==========
df = pd.DataFrame(data_list)

print("\n📊 DataFrame 信息:")
print(f"Shape: {df.shape}")
print(f"\n列名: {list(df.columns)}")
print(f"\n数据类型:\n{df.dtypes}")

value_list = df[['module', 'method']].value_counts().index.to_list()

df['test_data'].value_counts()

def func_a(i):

    a = df[(df['module'] == value_list[i][0]) & 
       (df['method'] == value_list[i][1])][
           ['database', 'object', 'object_id', 'module', 'method','command', 'test_data']]
    
    return a

i = 9
func_a(i).iloc[0]['test_data']
func_a(i)['test_data'].value_counts()

template_dict = {
    ("Tabs", "Select Tab"): {"template": "Select {object} in {database}"},

    ("Buttons", "Click Oneshot Button"): {"template": "Click {object} button"},

    ("Editor(s)", "Open Object"): {"template": "Open {object} of station {station_nummer}"},
    # when station_nummer is missing, it implies the default station

    ("Editor(s)", "Open Object with ID"): {"template": "Open {object} with id {object_id} of station {station_nummer} in {database}"},
   
    ("Editor(s)", "Verify Field"): {"template": "Verify {field} of {object} in {database}"},

    ("Editor(s)", "Switch Spatial Context"): {"template": "Switch {Spatial_Context} of {object} in {database}"},

    ("Hierarchy Viewer", "Select first HV object"): {"template": "Select first hierarchy {object} indexed {ID_HV} in {database}"},

    ("Hierarchy Viewer", "Select second HV object"): {"template": "Select second hierarchy {object} indexed {ID_HV} in {database}"},

    ("Datamodel Consistency Check", "Datamodel Check"): {"template": "Run datamodel consistency check in {database}"},
    
    ("Datamodel CRUD", "Create"): {"template": "Create {object} where {fields} have {values} in {database}"},
    # Or create list for {fields} & {values}
    ("Datamodel CRUD", "Update"): {"template": "Update {object} where {fields} have {values} in {database}"},

    ("Datamodel CRUD", "Delete"): {"template": "Delete {object} in {database}"},
}


class InstructionExtractor:
    """根据(module, method)组合和模板字典提取用户指令。"""

    def __init__(self, dataframe, templates):
        self.df = dataframe.copy()
        self.templates = templates

    def _clean_text(self, value):
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.lower() in {"none", "nan", "null"}:
            return ""
        return text

    def _clean_database(self, value):
        return self._clean_text(value).replace(":", "")

    def extract_station_nummer(self, test_data):
        """从嵌套test_data中提取 Station Nummer；不存在时返回空字符串。"""
        if not isinstance(test_data, dict):
            return ""

        for section_value in test_data.values():
            if not isinstance(section_value, dict):
                continue

            for field_value in section_value.values():
                if not isinstance(field_value, dict):
                    continue

                station_nummer = field_value.get("Station Nummer")
                station_nummer = self._clean_text(station_nummer)
                if station_nummer:
                    return station_nummer

        return ""

    def build_context(self, row):
        """把一行原始数据映射成模板渲染上下文。"""
        return {
            "database": self._clean_database(row.get("database", "")),
            "object": self._clean_text(row.get("object", "")),
            "object_id": self._clean_text(row.get("object_id", "")),
            "module": self._clean_text(row.get("module", "")),
            "method": self._clean_text(row.get("method", "")),
            "command": self._clean_text(row.get("command", "")),
            "station_nummer": self.extract_station_nummer(row.get("test_data", {})),
        }

    def render_instruction(self, row):
        """根据当前行所属组合选择模板并生成指令。"""
        pair = (row.get("module"), row.get("method"))
        template_info = self.templates.get(pair)
        if not template_info:
            return ""

        context = self.build_context(row)
        template = template_info.get("template", "")
        fallback_template = template_info.get("fallback_template")

        if fallback_template and "{station_nummer}" in template and not context["station_nummer"]:
            template = fallback_template

        try:
            return template.format(**context)
        except KeyError as exc:
            missing_field = exc.args[0]
            return f"[MISSING FIELD: {missing_field}]"

    def render_pair(self, pair, columns=None):
        """渲染某个(module, method)组合下的所有指令。"""
        group_df = self.df[
            (self.df["module"] == pair[0]) &
            (self.df["method"] == pair[1])
        ].copy()

        group_df["instruction"] = group_df.apply(self.render_instruction, axis=1)
        group_df["station_nummer"] = group_df["test_data"].apply(self.extract_station_nummer)
        group_df["database_clean"] = group_df["database"].apply(self._clean_database)

        if columns is None:
            columns = [
                "database",
                "object",
                "object_id",
                "module",
                "method",
                "station_nummer",
                "instruction",
            ]

        available_columns = [column for column in columns if column in group_df.columns]
        return group_df[available_columns]

    def render_by_index(self, i, columns=None):
        """通过value_list中的索引渲染对应组合。"""
        pair = value_list[i]
        return self.render_pair(pair, columns=columns)


extractor = InstructionExtractor(df, template_dict)

# 示例：查看第 i 个组合的渲染结果
rendered_df = extractor.render_by_index(i)
rendered_df.head()
