def dementia_result(score: int) -> str:
    if score >= 24:
        return "Normal Cognitive Function"
    elif score >= 18:
        return "Mild Cognitive Impairment"
    elif score >= 9:
        return "Moderate Cognitive Impairment"
    return "Severe Cognitive Impairment"
