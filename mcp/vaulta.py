"""
Vaulta MCP Server
Provides Model Context Protocol tools for interacting with Vaulta API
Based on OpenAPI spec from backend.vaultadigital.com
"""
import os
import json
import uuid
import logging
import requests
from typing import Any, Dict, List, Optional
from configs.config import get_active_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Vaulta API Configuration from centralized config
_cfg = get_active_config()
VAULTA_BASE_URL = _cfg.VAULTA_BASE_URL


class VaultaClient:
    """Client for Vaulta API interactions"""
    
    def __init__(self, base_url: str = None, access_token: str = None):
        self.base_url = base_url or VAULTA_BASE_URL
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
        if access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {access_token}'
            })
    
    def set_access_token(self, token: str):
        """Set or update the access token for authenticated requests"""
        self.access_token = token
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
    
    def _request(self, method: str, endpoint: str, data: Dict = None, 
                 params: Dict = None, auth_required: bool = True) -> Dict:
        """Make HTTP request to Vaulta API"""
        url = f"{self.base_url}{endpoint}"
        
        # Log request
        logger.info(f"📤 Vaulta Request: {method} {url}")
        if data:
            logger.info(f"   Data: {json.dumps(data, indent=2)}")
        if params:
            logger.info(f"   Params: {params}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params
            )
            
            # Log response
            logger.info(f"📥 Vaulta Response: {response.status_code}")
            try:
                response_json = response.json()
                logger.info(f"   Response: {json.dumps(response_json, indent=2)}")
            except:
                logger.info(f"   Response: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_detail = {}
            try:
                error_detail = e.response.json() if e.response else {}
            except:
                pass
            
            # Log error
            logger.error(f"❌ Vaulta Error: {str(e)}")
            if error_detail:
                logger.error(f"   Error Details: {json.dumps(error_detail, indent=2)}")
            
            return {
                'error': {
                    'message': str(e),
                    'status_code': e.response.status_code if e.response else None,
                    'details': error_detail
                }
            }
    
    # ============= AUTHENTICATION =============
    
    def login(self, email: str) -> Dict:
        """Login with email - returns temporary token and sends OTP"""
        return self._request('POST', '/login', 
                           data={'email': email},
                           auth_required=False)
    
    def verify_otp(self, otp: str, token: str) -> Dict:
        """Verify OTP and get access token"""
        return self._request('POST', '/verify-otp',
                           data={'otp': otp, 'token': token},
                           auth_required=False)
    
    def register(self, first_name: str, last_name: str, email: str, phone: str) -> Dict:
        """Register a new user"""
        register_response = self._request('POST', '/register',
                           data={
                               'first_name': first_name,
                               'last_name': last_name,
                               'email': email,
                               'phone': phone
                           },
                           auth_required=False)
        
        return register_response
    
    def get_current_user(self) -> Dict:
        """Get current authenticated user account info"""
        return self._request('GET', '/account')
    
    # ============= ACCOUNTS =============
    
    def create_account(self, name: str, currency: str = "USD", 
                      metadata: Dict = None) -> Dict:
        """Create a new Vaulta account"""
        data = {
            'name': name,
            'currency': currency
        }
        if metadata:
            data['metadata'] = metadata
        
        return self._request('POST', '/api/v1/create_account', data=data)
    
    def get_all_accounts(self) -> Dict:
        """Get all accounts for the authenticated user"""
        return self._request('GET', '/api/v1/accounts')
    
    def update_account(self, account_id: str, name: str, currency: str,
                      metadata: Dict = None) -> Dict:
        """Update an account"""
        data = {
            'name': name,
            'currency': currency
        }
        if metadata:
            data['metadata'] = metadata
        
        return self._request('PUT', f'/api/v1/accounts/{account_id}', data=data)
    
    def delete_account(self, account_id: str) -> Dict:
        """Delete an account"""
        return self._request('DELETE', f'/api/v1/accounts/{account_id}')
    
    # ============= PAYMENTS =============
    
    def create_payment(self, source_account_id: str, amount: str, 
                      currency: str, destination: Dict, 
                      description: str = None, client_reference: str = None) -> Dict:
        """Create a payment"""
        data = {
            'source_account_id': source_account_id,
            'amount': amount,
            'currency': currency,
            'destination': destination
        }
        if description:
            data['description'] = description
        if client_reference:
            data['client_reference'] = client_reference
        
        return self._request('POST', '/api/v1/payments', data=data)
    
    def get_payment(self, payment_id: str) -> Dict:
        """Get payment details"""
        return self._request('GET', f'/api/v1/payments/{payment_id}')
    
    def approve_payment(self, payment_id: str, admin_id: str, 
                       approved: bool, reason: str = None) -> Dict:
        """Approve or reject a payment (admin)"""
        data = {
            'admin_id': admin_id,
            'approved': approved
        }
        if reason:
            data['reason'] = reason
        
        return self._request('POST', f'/api/v1/payments/{payment_id}/approve', data=data)
    
    def get_pending_payments(self) -> Dict:
        """Get all pending payments (admin)"""
        return self._request('GET', '/api/v1/admin/payments/pending')
    
    def get_payment_transaction(self, payment_id: str) -> Dict:
        """Get the transaction associated with a payment"""
        return self._request('GET', f'/api/v1/payments/{payment_id}/transaction')
    
    # ============= TRANSACTIONS =============
    
    def create_transaction(self, amount: float, currency: str, 
                          transaction_type: str, status: str = "pending") -> Dict:
        """Create a single transaction"""
        return self._request('POST', '/api/v1/transaction',
                           data={
                               'amount': amount,
                               'currency': currency,
                               'type': transaction_type,
                               'status': status
                           })
    
    def create_transactions(self, amount: float, currency: str, 
                           transaction_type: str, status: str = "pending") -> Dict:
        """Create transactions (batch)"""
        return self._request('POST', '/api/v1/create_transactions',
                           data={
                               'amount': amount,
                               'currency': currency,
                               'type': transaction_type,
                               'status': status
                           })
    
    def get_all_transactions(self) -> Dict:
        """Get all transactions for the user"""
        return self._request('GET', '/api/v1/transactions')
    
    def get_transaction(self, transaction_id: str) -> Dict:
        """Get specific transaction details"""
        return self._request('GET', f'/api/v1/transactions/{transaction_id}')
    
    def update_transaction(self, transaction_id: str, amount: float = None,
                          currency: str = None, transaction_type: str = None,
                          status: str = None) -> Dict:
        """Update a transaction"""
        data = {}
        if amount is not None:
            data['amount'] = amount
        if currency:
            data['currency'] = currency
        if transaction_type:
            data['type'] = transaction_type
        if status:
            data['status'] = status
        
        return self._request('PUT', f'/api/v1/transactions/{transaction_id}', data=data)
    
    def delete_transaction(self, transaction_id: str) -> Dict:
        """Delete a transaction"""
        return self._request('DELETE', f'/api/v1/transactions/{transaction_id}')
    
    def get_all_admin_transactions(self) -> Dict:
        """Get all transactions (admin)"""
        return self._request('GET', '/api/v1/admin/transactions')
    
    # ============= QUOTES & TRADING =============
    
    def get_quote(self, pair: str, side: str, amount_crypto: float = None,
                 amount_fiat: float = None) -> Dict:
        """Get a trading quote"""
        data = {
            'pair': pair,
            'side': side
        }
        if amount_crypto is not None:
            data['amount_crypto'] = amount_crypto
        if amount_fiat is not None:
            data['amount_fiat'] = amount_fiat
        
        return self._request('POST', '/api/v1/get_quote', data=data)
    
    def get_pairs(self) -> Dict:
        """Get all available trading pairs"""
        return self._request('GET', '/api/v1/pairs')
    
    def get_cron_rates(self) -> Dict:
        """Get today's cron rates"""
        return self._request('GET', '/api/v1/cron_rates')
    
    # ============= API KEYS =============
    
    def create_api_key(self) -> Dict:
        """Create a new API key"""
        return self._request('POST', '/api/v1/create_api_key')
    
    def get_api_keys(self) -> Dict:
        """Get all API keys for the user"""
        return self._request('GET', '/api/v1/api_keys')
    
    def delete_api_key(self, api_key: str) -> Dict:
        """Delete an API key"""
        return self._request('DELETE', f'/api/v1/delete_api_key/{api_key}')
    
    def toggle_api_key(self, api_key: str, active: bool) -> Dict:
        """Toggle API key status (active/inactive)"""
        return self._request('POST', '/api/v1/toggle_api_key',
                           data={'api_key': api_key, 'active': active})
    
    # ============= ADMIN =============
    
    def get_all_users(self) -> Dict:
        """Get all users (admin)"""
        return self._request('GET', '/api/v1/admin/users')


# MCP Tool Definitions
class VaultaMCP:
    """MCP Server for Vaulta API"""
    
    def __init__(self, access_token: str = None):
        self.client = VaultaClient(access_token=access_token)
        self.tools = self._define_tools()
    
    def set_access_token(self, token: str):
        """Set access token for authenticated requests"""
        self.client.set_access_token(token)
    
    def _define_tools(self) -> List[Dict]:
        """Define MCP tools for Vaulta API"""
        return [
            {
                'name': 'vaulta_set_access_token',
                'description': 'Set the OAuth2 Bearer token for authenticated requests',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'token': {
                            'type': 'string',
                            'description': 'Bearer access token returned after OTP verification'
                        }
                    },
                    'required': ['token']
                }
            },
            {
                'name': 'vaulta_logout',
                'description': 'Logout by clearing the current bearer token',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_auth_status',
                'description': 'Check authentication status and return basic user info if logged in',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_login',
                'description': 'Login to Vaulta with email - sends OTP to email and returns temporary token',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'email': {
                            'type': 'string',
                            'description': 'User email address'
                        }
                    },
                    'required': ['email']
                }
            },
            {
                'name': 'vaulta_verify_otp',
                'description': 'Verify OTP code sent to email and get bearer access token',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'otp': {
                            'type': 'string',
                            'description': 'OTP code from email'
                        },
                        'token': {
                            'type': 'string',
                            'description': 'Temporary access_token received from login response'
                        }
                    },
                    'required': ['otp', 'token']
                }
            },
            {
                'name': 'vaulta_register',
                'description': 'Register a new user on Vaulta platform. After registration, user needs to login separately.',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'first_name': {
                            'type': 'string',
                            'description': 'User first name'
                        },
                        'last_name': {
                            'type': 'string',
                            'description': 'User last name'
                        },
                        'email': {
                            'type': 'string',
                            'description': 'User email address'
                        },
                        'phone': {
                            'type': 'string',
                            'description': 'User phone number'
                        }
                    },
                    'required': ['first_name', 'last_name', 'email', 'phone']
                }
            },
            {
                'name': 'vaulta_get_current_user',
                'description': 'Get current authenticated user account information and dashboard',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_create_account',
                'description': 'Create a new Vaulta account for holding funds',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'name': {
                            'type': 'string',
                            'description': 'Account name (e.g., "Main Trading Account")'
                        },
                        'currency': {
                            'type': 'string',
                            'default': 'USD',
                            'description': 'Account currency (default: USD)'
                        },
                        'metadata': {
                            'type': 'object',
                            'description': 'Optional metadata for custom tracking'
                        }
                    },
                    'required': ['name', 'currency']
                }
            },
            {
                'name': 'vaulta_get_all_accounts',
                'description': 'Get all accounts for the authenticated user with balances',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_update_account',
                'description': 'Update account details',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'account_id': {
                            'type': 'string',
                            'description': 'Account ID to update'
                        },
                        'name': {
                            'type': 'string',
                            'description': 'New account name'
                        },
                        'currency': {
                            'type': 'string',
                            'description': 'Account currency'
                        },
                        'metadata': {
                            'type': 'object',
                            'description': 'Optional metadata'
                        }
                    },
                    'required': ['account_id', 'name', 'currency']
                }
            },
            {
                'name': 'vaulta_delete_account',
                'description': 'Delete an account',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'account_id': {
                            'type': 'string',
                            'description': 'Account ID to delete'
                        }
                    },
                    'required': ['account_id']
                }
            },
            {
                'name': 'vaulta_create_payment',
                'description': 'Create a payment to a stablecoin address',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'source_account_id': {
                            'type': 'string',
                            'description': 'Source account ID to debit from'
                        },
                        'amount': {
                            'type': 'string',
                            'description': 'Payment amount (e.g., "100.00")'
                        },
                        'currency': {
                            'type': 'string',
                            'description': 'Currency code (e.g., "USD")'
                        },
                        'destination': {
                            'type': 'object',
                            'description': 'Payment destination details',
                            'properties': {
                                'rail': {
                                    'type': 'string',
                                    'description': 'Payment rail (e.g., "stablecoin")'
                                },
                                'network': {
                                    'type': 'string',
                                    'description': 'Blockchain network (e.g., "solana")'
                                },
                                'address': {
                                    'type': 'string',
                                    'description': 'Destination address'
                                }
                            },
                            'required': ['rail', 'network', 'address']
                        },
                        'description': {
                            'type': 'string',
                            'description': 'Optional payment description'
                        },
                        'client_reference': {
                            'type': 'string',
                            'description': 'Optional client reference ID'
                        }
                    },
                    'required': ['source_account_id', 'amount', 'currency', 'destination']
                }
            },
            {
                'name': 'vaulta_get_payment',
                'description': 'Get payment details by ID',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'payment_id': {
                            'type': 'string',
                            'description': 'Payment ID'
                        }
                    },
                    'required': ['payment_id']
                }
            },
            {
                'name': 'vaulta_get_quote',
                'description': 'Get a trading quote for crypto/fiat pair',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'pair': {
                            'type': 'string',
                            'description': 'Trading pair (e.g., "BTC-USD")'
                        },
                        'side': {
                            'type': 'string',
                            'enum': ['buy', 'sell'],
                            'description': 'Trade side: buy or sell'
                        },
                        'amount_crypto': {
                            'type': 'number',
                            'description': 'Amount in crypto (if buying crypto)'
                        },
                        'amount_fiat': {
                            'type': 'number',
                            'description': 'Amount in fiat (if selling crypto)'
                        }
                    },
                    'required': ['pair', 'side']
                }
            },
            {
                'name': 'vaulta_get_pairs',
                'description': 'Get all available trading pairs',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_get_cron_rates',
                'description': 'Get today\'s exchange rates',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_create_transaction',
                'description': 'Create a single transaction record',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'amount': {
                            'type': 'number',
                            'description': 'Transaction amount'
                        },
                        'currency': {
                            'type': 'string',
                            'description': 'Currency code'
                        },
                        'transaction_type': {
                            'type': 'string',
                            'description': 'Transaction type (e.g., "deposit", "withdrawal")'
                        },
                        'status': {
                            'type': 'string',
                            'default': 'pending',
                            'description': 'Transaction status'
                        }
                    },
                    'required': ['amount', 'currency', 'transaction_type']
                }
            },
            {
                'name': 'vaulta_get_all_transactions',
                'description': 'Get all transactions for the user',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_get_transaction',
                'description': 'Get specific transaction by ID',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'transaction_id': {
                            'type': 'string',
                            'description': 'Transaction ID'
                        }
                    },
                    'required': ['transaction_id']
                }
            },
            {
                'name': 'vaulta_create_api_key',
                'description': 'Create a new API key for programmatic access',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'vaulta_get_api_keys',
                'description': 'Get all API keys for the user',
                'input_schema': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            }
        ]
    
    def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Execute a tool call"""
        
        method_map = {
            'vaulta_set_access_token': lambda: self._handle_set_token(**arguments),
            'vaulta_login': lambda: self._handle_login(**arguments),
            'vaulta_verify_otp': lambda: self._handle_verify_otp(**arguments),
            'vaulta_logout': lambda: self._handle_logout(),
            'vaulta_auth_status': lambda: self._handle_auth_status(),
            'vaulta_register': lambda: self.client.register(**arguments),
            'vaulta_get_current_user': lambda: self.client.get_current_user(),
            'vaulta_create_account': lambda: self.client.create_account(**arguments),
            'vaulta_get_all_accounts': lambda: self.client.get_all_accounts(),
            'vaulta_update_account': lambda: self.client.update_account(**arguments),
            'vaulta_delete_account': lambda: self.client.delete_account(**arguments),
            'vaulta_create_payment': lambda: self.client.create_payment(**arguments),
            'vaulta_get_payment': lambda: self.client.get_payment(**arguments),
            'vaulta_get_quote': lambda: self.client.get_quote(**arguments),
            'vaulta_get_pairs': lambda: self.client.get_pairs(),
            'vaulta_get_cron_rates': lambda: self.client.get_cron_rates(),
            'vaulta_create_transaction': lambda: self.client.create_transaction(**arguments),
            'vaulta_get_all_transactions': lambda: self.client.get_all_transactions(),
            'vaulta_get_transaction': lambda: self.client.get_transaction(**arguments),
            'vaulta_create_api_key': lambda: self.client.create_api_key(),
            'vaulta_get_api_keys': lambda: self.client.get_api_keys()
        }
        
        if tool_name not in method_map:
            return {'error': f'Tool {tool_name} not found'}
        
        try:
            return method_map[tool_name]()
        except Exception as e:
            return {'error': str(e)}

    def _extract_token_from_response(self, resp: Dict) -> Optional[str]:
        """Try to extract an access token from various possible response shapes."""
        if not isinstance(resp, dict):
            return None
        # Direct keys
        for key in ['access_token', 'token', 'bearer', 'accessToken']:
            if key in resp and isinstance(resp[key], str) and resp[key]:
                return resp[key]
        # Nested in 'data'
        data = resp.get('data') if isinstance(resp.get('data'), dict) else None
        if data:
            for key in ['access_token', 'token', 'bearer', 'accessToken']:
                if key in data and isinstance(data[key], str) and data[key]:
                    return data[key]
        return None

    def _handle_verify_otp(self, otp: str, token: str) -> Dict:
        """Verify OTP and automatically set bearer token if returned."""
        resp = self.client.verify_otp(otp=otp, token=token)
        access_token = self._extract_token_from_response(resp)
        if access_token:
            self.client.set_access_token(access_token)
            # Also echo token back for higher-level session handling if needed
            resp = {**resp, 'access_token': access_token}
        return resp

    def _handle_set_token(self, token: str) -> Dict:
        """Set bearer token explicitly from the caller."""
        self.client.set_access_token(token)
        return {'status': 'ok', 'message': 'Access token set'}
    
    def _handle_login(self, email: str) -> Dict:
        """Login with email - returns temporary token for OTP verification.
        
        The response contains:
        - message: Status message
        - access_token: Temporary token to use with verify_otp
        - token_type: "bearer"
        """
        resp = self.client.login(email=email)
        # Don't set the token yet - it's temporary until OTP is verified
        return resp

    def _handle_logout(self) -> Dict:
        """Clear current bearer token (client-side logout)."""
        self.client.access_token = None
        # Remove Authorization header if present
        if 'Authorization' in self.client.session.headers:
            self.client.session.headers.pop('Authorization', None)
        return {'status': 'ok', 'message': 'Logged out'}

    def _handle_auth_status(self) -> Dict:
        """Return authentication status and minimal user info if possible."""
        if not self.client.access_token:
            return {'authenticated': False}
        # Try fetching current user details
        user_resp = self.client.get_current_user()
        if user_resp.get('error'):
            return {'authenticated': False, 'error': user_resp.get('error')}
        user_info = user_resp.get('user', {})
        accounts = user_resp.get('accounts', [])
        return {
            'authenticated': True,
            'email': user_info.get('email'),
            'name': f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
            'accounts_count': len(accounts)
        }


# Initialize MCP server instance
vaulta_mcp = VaultaMCP()
