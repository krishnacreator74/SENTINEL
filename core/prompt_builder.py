
"""
Prompt Builder for Sentinel AI
Handles prompt construction and template management
"""

from typing import Dict, List, Optional, Any


class PromptTemplate:
    """Template for building prompts"""
    
    def __init__(self, name: str, base: str):
        self.name = name
        self.base = base
        self.variables: Dict[str, str] = {}
    
    def set_variable(self, key: str, value: str):
        """Set a template variable"""
        self.variables[key] = value
    
    def render(self) -> str:
        """Render the template with current variables"""
        result = self.base
        for key, value in self.variables.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        return result


class PromptBuilder:
    """Builder for constructing AI prompts"""
    
    def __init__(self):
        self.templates: Dict[str, PromptTemplate] = {}
        self.system_prompt: Optional[str] = None
    
    def register_template(self, name: str, template: str) -> PromptTemplate:
        """Register a new prompt template"""
        prompt = PromptTemplate(name, template)
        self.templates[name] = prompt
        return prompt
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name"""
        return self.templates.get(name)
    
    def build_prompt(self, template_name: str, **kwargs) -> str:
        """Build a prompt from a registered template"""
        template = self.get_template(template_name)
        if not template:
            raise ValueError(f"Template '{template_name}' not found")
        
        for key, value in kwargs.items():
            template.set_variable(key, str(value))
        
        return template.render()
    
    def set_system_prompt(self, prompt: str):
        """Set the system prompt"""
        self.system_prompt = prompt
    
    def get_system_prompt(self) -> Optional[str]:
        """Get the system prompt"""
        return self.system_prompt


# Common prompt templates
default_system_prompt = """You are Sentinel, an AI assistant. 
{{role_description}}
{{instructions}}

Remember:
- {{do_not_forget}}
- {{conversation_context}}"""


def get_default_builder() -> PromptBuilder:
    """Get a default prompt builder with common templates"""
    builder = PromptBuilder()
    builder.set_system_prompt(default_system_prompt)
    
    # Register common templates
    builder.register_template(
        "standard_response",
        """Based on the conversation history and context:
{{context}}

{{user_message}}

{{your_response}}"""
    )
    
    return builder
