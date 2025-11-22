"""
Status codes for conversation flow tracking
All authentication is handled by Vaulta
"""

class ConversationStatus:
    """Status codes to indicate where user is in the conversation flow"""
    
    # Authentication states (Vaulta only)
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    AWAITING_OTP = "AWAITING_OTP"
    AUTHENTICATED = "AUTHENTICATED"
    
    # Payment flow states
    PAYMENT_SELECTING_ACCOUNT = "PAYMENT_SELECTING_ACCOUNT"
    PAYMENT_ENTERING_AMOUNT = "PAYMENT_ENTERING_AMOUNT"
    PAYMENT_ENTERING_CURRENCY = "PAYMENT_ENTERING_CURRENCY"
    PAYMENT_ENTERING_DESTINATION = "PAYMENT_ENTERING_DESTINATION"
    PROCESSING_PAYMENT = "PROCESSING_PAYMENT"
    PAYMENT_COMPLETE = "PAYMENT_COMPLETE"
    
    # Account creation states
    CREATING_VAULTA_ACCOUNT = "CREATING_VAULTA_ACCOUNT"
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    
    # Trading/Quote states
    GETTING_QUOTE = "GETTING_QUOTE"
    QUOTE_RECEIVED = "QUOTE_RECEIVED"
    
    # General states
    VAULTA_ACTIVE = "VAULTA_ACTIVE"
    VIEWING_ACCOUNTS = "VIEWING_ACCOUNTS"
    VIEWING_TRANSACTIONS = "VIEWING_TRANSACTIONS"
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    ERROR = "ERROR"


def determine_status(session: dict, user_context: dict = None) -> str:
    """
    Determine conversation status based on Vaulta authentication and current activity
    
    Args:
        session: Current chat session
        user_context: User authentication context from Vaulta
    
    Returns:
        Status code string
    """
    if not session:
        return ConversationStatus.NOT_AUTHENTICATED
    
    # If an explicit update_status tool call exists in history, prefer its last value
    if session.get('history'):
        for interaction in reversed(session['history']):
            tool_calls = interaction.get('tool_calls', [])
            for tc in reversed(tool_calls):
                if tc.get('function') == 'update_status':
                    # Try arguments first, then result
                    explicit = (tc.get('arguments', {}) or {}).get('status') or (tc.get('result', {}) or {}).get('status')
                    if explicit and hasattr(ConversationStatus, explicit):
                        return getattr(ConversationStatus, explicit)
                    if explicit:
                        return explicit  # Return as-is even if not predefined
                    break

    # Check if user is authenticated with Vaulta
    if not user_context or not user_context.get('email'):
        # Check if waiting for OTP
        if session.get('history'):
            last_interaction = session['history'][-1]
            last_tools = last_interaction.get('tool_calls', [])
            if last_tools and last_tools[-1].get('function') == 'vaulta_login':
                return ConversationStatus.AWAITING_OTP
        return ConversationStatus.NOT_AUTHENTICATED
    
    # User is authenticated - check what they're doing
    if session.get('history'):
        last_interaction = session['history'][-1]
        assistant_message = last_interaction.get('assistant', '').lower()
        tool_calls = last_interaction.get('tool_calls', [])
        
        # Analyze assistant's last message to determine state
        # Payment flow detection
        if 'which account would you like to pay from' in assistant_message or \
           'which account do you want to use' in assistant_message:
            return ConversationStatus.PAYMENT_SELECTING_ACCOUNT
        
        if 'how much would you like to send' in assistant_message or \
           'what amount' in assistant_message:
            return ConversationStatus.PAYMENT_ENTERING_AMOUNT
        
        if 'what currency' in assistant_message and 'payment' in assistant_message:
            return ConversationStatus.PAYMENT_ENTERING_CURRENCY
        
        if ('destination' in assistant_message or 'where should i send' in assistant_message or \
            'what type of payment' in assistant_message or 'which network' in assistant_message) and \
           any(word in assistant_message for word in ['payment', 'send', 'transfer']):
            return ConversationStatus.PAYMENT_ENTERING_DESTINATION
        
        # Check most recent tool calls
        if tool_calls:
            last_tool = tool_calls[-1].get('function', '')
            
            # Payment completed
            if last_tool == 'vaulta_create_payment':
                result = tool_calls[-1].get('result', {})
                if not result.get('error'):
                    return ConversationStatus.PAYMENT_COMPLETE
                return ConversationStatus.ERROR
            
            # Account operations
            if last_tool == 'vaulta_create_account':
                result = tool_calls[-1].get('result', {})
                if not result.get('error'):
                    return ConversationStatus.ACCOUNT_CREATED
                return ConversationStatus.CREATING_VAULTA_ACCOUNT
            
            if last_tool == 'vaulta_get_all_accounts':
                return ConversationStatus.VIEWING_ACCOUNTS
            
            # Transactions
            if last_tool == 'vaulta_get_all_transactions':
                return ConversationStatus.VIEWING_TRANSACTIONS
            
            # Trading/Quotes
            if last_tool == 'vaulta_get_quote':
                return ConversationStatus.QUOTE_RECEIVED
            
            if last_tool == 'vaulta_get_pairs':
                return ConversationStatus.GETTING_QUOTE
            
            # General Vaulta activity
            if last_tool.startswith('vaulta_'):
                return ConversationStatus.VAULTA_ACTIVE
    
    # Default authenticated state
    return ConversationStatus.AUTHENTICATED
