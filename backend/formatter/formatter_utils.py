from ML.predictor import predict_line_type

def format_document(lines, template):
    formatted_lines = []

    for line in lines:
        if not line.strip():
            continue

        label = predict_line_type(line)

        styled_line = apply_template_style(line, label, template)
        formatted_lines.append(styled_line)

    return formatted_lines