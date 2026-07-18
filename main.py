from ppt_template_parser import PPTTemplateParser



input_ppt = (
    "input/research_report.pptx"
)



output_json = (
    "output/template.json"
)



parser = PPTTemplateParser(
    input_ppt
)

from theme_parser import PPTThemeParser



theme_parser = PPTThemeParser(
    "input/research_report.pptx"
)


theme = theme_parser.parse()


print(theme)

parser.save_json(
    output_json
)
