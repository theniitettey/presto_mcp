"""
Status MCP Server
Provides a tool for explicitly updating conversation status codes.
The AI should call this instead of embedding status codes in user-visible replies.
"""
from typing import Dict, List
from configs.status import ConversationStatus


class StatusMCP:
    """MCP Server for conversation status management"""

    def __init__(self):
        self.current_status = None
        self.tools = self._define_tools()

    def _define_tools(self) -> List[Dict]:
        # Dynamically build enum list from ConversationStatus values
        status_values = [v for k, v in ConversationStatus.__dict__.items() if not k.startswith('_') and isinstance(v, str)]
        return [
            {
                'name': 'update_status',
                'description': 'Update the current conversation status (internal only; never display status codes to user).',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'status': {
                            'type': 'string',
                            'enum': status_values,
                            'description': 'The conversation status code to set.'
                        }
                    },
                    'required': ['status']
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        if tool_name != 'update_status':
            return {'error': f'Tool {tool_name} not found'}
        status = arguments.get('status')
        if not status:
            return {'error': 'Missing status'}
        self.current_status = status
        return {'status': status, 'updated': True}


# Global instance
status_mcp = StatusMCP()
