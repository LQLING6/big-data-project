class EmailProvider:
    def send(self, to_email: str, subject: str, content: str) -> bool:
        # 任务书要求：本地测试收件箱适配器，不需要真发
        # 你可以在这里把邮件内容写到一个本地 .txt 或 .json 文件里
        print(f"模拟发送邮件给 {to_email}: {subject}")
        return True # 模拟发送成功