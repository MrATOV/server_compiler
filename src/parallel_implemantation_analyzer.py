import json
from typing import Dict, List, Any

def analyze_parallel_performance(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    global_comments = []

    for dataset in input_data:
        analyzed_dataset = dataset.copy()
        analyzed_data = []
        dataset_comments = []
        
        for item in dataset["data"]:
            analyzed_item = item.copy()
            performance_data = item["performance"]
            sequential_run = next((run for run in performance_data if run["thread"] == 1), None)
            
            if not sequential_run:
                continue
            
            sequential_time = sequential_run["time"]
            analysis_entries = []
            
            for run in performance_data:
                if run["thread"] == 1:
                    continue
                
                p_amdahl = run.get("amdahl_p", 0)
                p_gustavson = run.get("gustavson_p", 0)
                
                amdahl_acceleration = None
                gustavson_acceleration = None
                
                if p_amdahl is not None and p_amdahl != -1:
                    amdahl_acceleration = 1 / ((1 - p_amdahl) + (p_amdahl/run["thread"]))
                    run["amdahl_acceleration"] = round(amdahl_acceleration, 2)
                    if "amdahl_p" in run:
                        del run["amdahl_p"]
                
                if p_gustavson is not None and p_gustavson != -1:
                    gustavson_acceleration = run["thread"] + (1 - run["thread"]) * p_gustavson
                    run["gustavson_acceleration"] = round(gustavson_acceleration, 2)
                    if "gustavson_p" in run:
                        del run["gustavson_p"]
                
                actual_acceleration = run["acceleration"]
                
                expected_acceleration = None
                if p_gustavson is not None and p_gustavson != -1 and p_gustavson > 0.9:
                    expected_acceleration = gustavson_acceleration
                elif p_amdahl is not None and p_amdahl != -1:
                    expected_acceleration = amdahl_acceleration
                
                if expected_acceleration is not None:
                    efficiency = (actual_acceleration / expected_acceleration) * 100
                    run["efficiency"] = round(efficiency, 1) if round(efficiency, 1) is not None else 0

                    task_type = "масштабируемая (Густавсон-Барсис)" if (p_gustavson is not None and p_gustavson != -1 and p_gustavson > 0.9) else "фиксированная (Амдал)"
                    theory_law = "Густавсона-Барсиса" if (p_gustavson is not None and p_gustavson != -1 and p_gustavson > 0.9) else "Амдала"
                    theory_acceleration = gustavson_acceleration if (p_gustavson is not None and p_gustavson != -1 and p_gustavson > 0.9) else amdahl_acceleration
                    
                    comment_parts = [
                        f"Для {run['thread']} потоков:",
                        f"Фактическое ускорение: {actual_acceleration:.2f}x",
                        f"Ожидаемое по закону {theory_law}: {theory_acceleration:.2f}x",
                        f"Эффективность: {efficiency:.1f}%",
                        f"Тип задачи: {task_type}"
                    ]
                    
                    if efficiency < 80:
                        if efficiency < 50:
                            diagnosis = "СИЛЬНОЕ НЕСООТВЕТСТВИЕ - возможны проблемы синхронизации или нагрузка на общие ресурсы"
                        else:
                            diagnosis = "УМЕРЕННОЕ НЕСООТВЕТСТВИЕ - возможны накладные расходы параллелизации"
                        comment_parts.append(f"Диагноз: {diagnosis}")
                    
                    dataset_comments.append(" | ".join(comment_parts))
            
            if not dataset_comments:
                analyzed_item["analysis"] = "Параллельная реализация показывает хорошую эффективность (>80%) во всех тестах"
            else:
                analyzed_item["analysis"] = "\n".join(dataset_comments)
            
            analyzed_data.append(analyzed_item)
        
        effective_tests = sum(1 for item in analyzed_data if "хорошую эффективность" in item.get("analysis", ""))
        total_tests = len(analyzed_data)
        
        if effective_tests == total_tests:
            global_comments.append(
                f"Все {total_tests} тестов в '{dataset.get('title', '')}' успешны "
                f"(эффективность >80% для всех параллельных запусков)"
            )
        else:
            issues = total_tests - effective_tests
            global_comments.append(
                f"В '{dataset.get('title', '')}' проблемы в {issues} из {total_tests} тестов: "
                f"эффективность ниже 80% для {issues} конфигураций потоков"
            )
        
        analyzed_dataset["data"] = analyzed_data
        results.append(analyzed_dataset)
    
    if results:
        output = {
            "results": results,
            "global_analysis": "\n".join(global_comments)
        }
        return output
    return results