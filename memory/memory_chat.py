class ChatMemory:
    def __init__(self, max_messages=20):
        self.messages = []
        self.max_messages = max_messages

    def add_user(self, text):
        self.messages.append({
            "role": "user",
            "content": text
        })
        self._trim()

    def add_assistant(self, text):
        self.messages.append({
            "role": "assistant",
            "content": text
        })
        self._trim()

    def get_messages(self):
        return self.messages

    def clear(self):
        self.messages = []

    def _trim(self):
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]