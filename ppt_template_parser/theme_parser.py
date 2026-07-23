import zipfile
from lxml import etree


class PPTThemeParser:

    """
    解析PPTX主题:
    - 字体
    - 配色
    """


    NS = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main"
    }


    def __init__(self, pptx_path):

        self.pptx_path = pptx_path


    def _read_theme_xml(self):

        with zipfile.ZipFile(
            self.pptx_path,
            "r"
        ) as z:

            theme_files = [
                x for x in z.namelist()
                if "theme/theme" in x
                and x.endswith(".xml")
            ]


            if not theme_files:
                return None


            xml = z.read(
                theme_files[0]
            )

            return etree.fromstring(xml)



    def parse_colors(self):

        """
        读取主题颜色
        """

        root = self._read_theme_xml()

        if root is None:
            return {}


        colors = {}


        clr_scheme = root.find(
            ".//a:clrScheme",
            self.NS
        )


        if clr_scheme is None:
            return colors


        for item in clr_scheme:

            name = item.tag.split("}")[-1]


            child = item[0]


            # srgb颜色

            if "srgbClr" in child.tag:

                value = child.attrib.get(
                    "val"
                )

                colors[name] = (
                    "#" + value
                )


            # 主题颜色

            elif "sysClr" in child.tag:

                value = child.attrib.get(
                    "lastClr"
                )

                colors[name] = (
                    "#" + value
                )


        return colors



    def parse_fonts(self):

        """
        读取主题字体
        """

        root = self._read_theme_xml()

        if root is None:
            return {}


        fonts = {}


        major = root.find(
            ".//a:themeElements/a:fontScheme/a:majorFont",
            self.NS
        )


        minor = root.find(
            ".//a:themeElements/a:fontScheme/a:minorFont",
            self.NS
        )


        def extract(font_node):

            result={}

            if font_node is None:
                return result


            latin = font_node.find(
                "a:latin",
                self.NS
            )


            ea = font_node.find(
                "a:ea",
                self.NS
            )


            if latin is not None:

                result["latin"] = (
                    latin.attrib.get(
                        "typeface"
                    )
                )


            if ea is not None:

                result["east_asia"] = (
                    ea.attrib.get(
                        "typeface"
                    )
                )


            return result



        fonts["title"] = extract(
            major
        )

        fonts["body"] = extract(
            minor
        )


        return fonts



    def parse(self):

        return {

            "colors":
                self.parse_colors(),


            "fonts":
                self.parse_fonts()

        }