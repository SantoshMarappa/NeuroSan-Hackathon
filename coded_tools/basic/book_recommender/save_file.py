from neuro_san.interfaces.coded_tool import CodedTool

class FileSaveTool(CodedTool):
    def __init__(self):
        self.directory = 'C:/santosh/testfolder'

    def invoke(self, args: dict, sly_data: dict) -> str:
        file_name: str = args.get('file_name')
        content = args.get('content')
        file_path = f"{self.directory}/{file_name}"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return "Done"
        except Exception as e:
            return f"Failed to save file: {e}"

    async def async_invoke(self, args: dict, sly_data: dict) -> str:
        return self.invoke(args, sly_data)