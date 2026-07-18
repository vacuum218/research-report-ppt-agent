from pptx.enum.shapes import MSO_SHAPE_TYPE


class ShapeStyleParser:


    """
    PPT元素视觉样式解析

    读取:
    - 填充色
    - 边框
    - 透明度
    - 字体
    - 对齐
    """



    def parse(self, shape):


        result = {

            "fill": None,

            "line": None,

            "text": None

        }



        # ----------------
        # 填充
        # ----------------

        result["fill"] = self.parse_fill(
            shape
        )


        # ----------------
        # 边框
        # ----------------

        result["line"] = self.parse_line(
            shape
        )


        # ----------------
        # 文本
        # ----------------

        if shape.has_text_frame:

            result["text"] = (
                self.parse_text(
                    shape
                )
            )


        return result




    # ====================
    # Fill
    # ====================

    def parse_fill(self,shape):


        try:

            fill = shape.fill


            if fill.type is None:
                return None



            result={

                "type":
                str(fill.type)

            }



            if fill.fore_color.type:

                result["color"] = (
                    str(
                        fill.fore_color.rgb
                    )
                )


            return result


        except Exception:

            return None





    # ====================
    # Line
    # ====================

    def parse_line(self,shape):


        try:

            line = shape.line


            result={

                "width":
                str(line.width)

            }


            if line.color.type:

                result["color"] = (
                    str(
                        line.color.rgb
                    )
                )


            return result


        except Exception:

            return None





    # ====================
    # Text Style
    # ====================


    def parse_text(self,shape):


        result={

            "paragraphs":[]

        }



        for p in shape.text_frame.paragraphs:


            para={

                "alignment":
                str(
                    p.alignment
                ),


                "runs":[]

            }



            for r in p.runs:


                run={

                    "text":
                    r.text,


                    "font":
                    r.font.name,


                    "size":
                    str(
                        r.font.size
                    ),


                    "bold":
                    r.font.bold,


                    "italic":
                    r.font.italic

                }


                if r.font.color.type:

                    run["color"] = (
                        str(
                        r.font.color.rgb
                        )
                    )


                para["runs"].append(
                    run
                )



            result["paragraphs"].append(
                para
            )



        return result