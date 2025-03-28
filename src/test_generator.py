from src.schemas import TestDataRequest

def alpha(val):
    if val == 0:
        return "Alpha::percent90"
    elif val == 1:
        return "Alpha::percent95"
    else:
        return "Alpha::percent99"
    
def interval(val):
    if val == 1:
        return "IntervalType::StudentCoefficient"
    else:
        return "IntervalType::CD"

def calc(val):
    if val == 1:
        return "CalcValue::Median"
    elif val == 2:
        return "CalcValue::Mode"
    else:
        return "CalcValue::Mean"

def save(val):
    if val == 1:
        return "SaveOption::saveAll"
    elif val == 2:
        return "SaveOption::saveArgs"
    if val == 0:
        return "SaveOption::notSave"
    
def threads(vals):
    if not vals:
        return "{}"
    return "{" + ", ".join(map(str, vals)) + "}"

def constructor(type, filename):
    if type == 'array':
        return f"DataArray1D<!>(\"{filename}\")"
    if type == 'matrix':
        return f"DataMatrix<!>(\"{filename}\")"
    if type == 'text':
        return f"DataText(\"{filename}\")"
    if type == 'image':
        return f"DataImage(\"{filename}\")"
    if type == 'audio':
        return f"DataAudio(\"{filename}\")"
    if type == 'video':
        return f"DataVideo(\"{filename}\")"

def format_value(value):
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)

def include_type(type):
    if type == 'array':
        return "#include <TestingData/DataArray.h>"
    if type == 'matrix':
        return "#include <TestingData/DataMatrix.h>"
    if type == 'text':
        return "#include <TestingData/DataText.h>"
    if type == 'image':
        return "#include <TestingData/DataImage.h>"
    if type == 'audio':
        return "#include <TestingData/DataAudio.h>"
    if type == 'video':
        return "#include <TestingData/DataVideo.h>"

def generate_includes(cpp_code, type):
    includes_to_add = [
        "#include <ParallelTesting/TestOptions.h>",
        "#include <ParallelTesting/TestFunctions.h>",
        "#include <TestingData/Data.h>",
        include_type(type)
    ]
    
    existing_includes = set()
    
    for line in cpp_code.splitlines():
        line = line.strip()
        if line.startswith("#include"):
            existing_includes.add(line)

    final_includes = []
    for include in includes_to_add:
        if include not in existing_includes:
            final_includes.append(include)

    return "\n".join(final_includes)

def generate_main(data: TestDataRequest):
    text = "int main() {\n"
    op = data.options
    text += f"    TestOptions options({threads(op.threads)},\n"
    text += f"        {op.iterations}, {alpha(op.alpha)},\n"
    text += f"        {interval(op.koefficient)},\n"
    text += f"        {calc(op.calculate)},\n"
    text += f"        {save(op.saveResult)}, true\n"
    text += "    );\n"
    text += "    DataManager dataManager({\n"
    for file in data.files:
        text += f"        {constructor(data.type, file)},\n"
    text += "    });\n"

    if data.parameters:
        parameters_str = []
        for parameters in data.parameters:
            param_values = [format_value(value) for value in parameters.values()]
            parameters_str.append(", ".join(param_values))
        
        text += f"    FunctionManager functionManager({data.name}, {parameters_str.pop()});\n"
        
        if parameters_str:
            text += "    functionManager.add_arguments_set({\n"
            text += ",\n".join(f"        {{{param}}}" for param in parameters_str)
            text += "\n    });\n"
    else:
        text += f"    FunctionManager functionManager({data.name});\n"

    text += "    TestFunctions test(options, dataManager, functionManager);\n"
    text += "    test.run();\n"
    text += "    return 0;\n"
    text += "}"
    return text

def generate_data(data: TestDataRequest):
    return {
        "main": generate_main(data),
        "include": generate_includes(data.code, data.type)
    }