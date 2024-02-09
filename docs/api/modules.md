# Tasks list

Hereafter we provide the complete list of task name and their corresponding module in the ROMI libraries:

```python exec="1"
from romitask.modules import MODULES
md = "| Name | Module |\n"
md += "| ---- | ------ |\n"
for name, module in MODULES.items():
    md += f"| {name} | `{module}` |\n"
print(md)
```