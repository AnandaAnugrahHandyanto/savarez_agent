import json
import os
import requests
from tools.registry import registry

def check_requirements() -> bool:
    """Check if Reddit API credentials are available"""
    return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET") and os.getenv("REDDIT_USER_AGENT"))

def reddit_search(query: str, subreddit: str = None, limit: int = 10, sort: str = "relevance", time_filter: str = "all") -> str:
    """
    Search Reddit for posts and comments
    
    Args:
        query: Search query string
        subreddit: Optional subreddit to search in (e.g., 'python', 'technology')
        limit: Maximum number of results (1-100)
        sort: Sort method: 'relevance', 'hot', 'top', 'new', 'comments'
        time_filter: Time filter for 'top' sort: 'all', 'day', 'week', 'month', 'year', 'hour'
    
    Returns:
        JSON string with search results
    """
    try:
        # Get Reddit API credentials
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT")
        
        if not all([client_id, client_secret, user_agent]):
            return json.dumps({"error": "Missing Reddit API credentials. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT"})
        
        # Get access token
        auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': user_agent}
        
        response = requests.post('https://www.reddit.com/api/v1/access_token',
                               auth=auth, data=data, headers=headers)
        
        if response.status_code != 200:
            return json.dumps({"error": f"Failed to get access token: {response.text}"})
        
        access_token = response.json()['access_token']
        headers['Authorization'] = f'bearer {access_token}'
        
        # Build URL: use subreddit listing if browsing (no query), search if query given
        if not query and subreddit:
            # Browse subreddit directly — no search term needed
            valid_sorts = ['hot', 'new', 'top', 'rising', 'controversial']
            listing_sort = sort if sort in valid_sorts else 'hot'
            base_url = f"https://oauth.reddit.com/r/{subreddit}/{listing_sort}"
            params = {'limit': min(limit, 100)}
            if listing_sort == 'top' and time_filter != 'all':
                params['t'] = time_filter
        elif subreddit:
            # Search within a specific subreddit — use /r/{subreddit}/search
            base_url = f"https://oauth.reddit.com/r/{subreddit}/search"
            params = {
                'q': query,
                'limit': min(limit, 100),
                'sort': sort,
                'type': 'link',
                'restrict_sr': 'true'
            }
            if sort == 'top' and time_filter != 'all':
                params['t'] = time_filter
        else:
            # Global Reddit search
            base_url = "https://oauth.reddit.com/search"
            params = {
                'q': query,
                'limit': min(limit, 100),
                'sort': sort,
                'type': 'link'
            }
            if sort == 'top' and time_filter != 'all':
                params['t'] = time_filter
        
        # Make API request
        response = requests.get(base_url, params=params, headers=headers)
        
        if response.status_code != 200:
            return json.dumps({"error": f"API request failed: {response.text}"})
        
        # Process results
        data = response.json()
        results = []
        
        for post in data.get('data', {}).get('children', []):
            post_data = post.get('data', {})
            results.append({
                'title': post_data.get('title', ''),
                'subreddit': post_data.get('subreddit', ''),
                'author': post_data.get('author', ''),
                'score': post_data.get('score', 0),
                'upvote_ratio': post_data.get('upvote_ratio', 0),
                'num_comments': post_data.get('num_comments', 0),
                'created_utc': post_data.get('created_utc', 0),
                'url': post_data.get('url', ''),
                'permalink': f"https://reddit.com{post_data.get('permalink', '')}",
                'selftext': post_data.get('selftext', ''),
                'is_self': post_data.get('is_self', False),
                'stickied': post_data.get('stickied', False),
                'locked': post_data.get('locked', False),
                'over_18': post_data.get('over_18', False),
                'spoiler': post_data.get('spoiler', False)
            })
        
        return json.dumps({
            "success": True,
            "query": query,
            "subreddit": subreddit,
            "sort": sort,
            "limit": limit,
            "total_results": len(results),
            "results": results
        })
        
    except Exception as e:
        return json.dumps({"error": f"Reddit search failed: {str(e)}"})

def reddit_subreddit_info(subreddit: str) -> str:
    """
    Get information about a subreddit
    
    Args:
        subreddit: Subreddit name
    
    Returns:
        JSON string with subreddit information
    """
    try:
        # Get Reddit API credentials
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT")
        
        if not all([client_id, client_secret, user_agent]):
            return json.dumps({"error": "Missing Reddit API credentials. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT"})
        
        # Get access token
        auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': user_agent}
        
        response = requests.post('https://www.reddit.com/api/v1/access_token',
                               auth=auth, data=data, headers=headers)
        
        if response.status_code != 200:
            return json.dumps({"error": f"Failed to get access token: {response.text}"})
        
        access_token = response.json()['access_token']
        headers['Authorization'] = f'bearer {access_token}'
        
        # Get subreddit info
        url = f"https://oauth.reddit.com/r/{subreddit}/about"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 404:
            return json.dumps({"error": f"Subreddit '{subreddit}' not found"})
        
        if response.status_code != 200:
            return json.dumps({"error": f"Failed to get subreddit info: {response.text}"})
        
        data = response.json().get('data', {})
        
        return json.dumps({
            "success": True,
            "subreddit": subreddit,
            "title": data.get('title', ''),
            "description": data.get('public_description', ''),
            "subscribers": data.get('subscribers', 0),
            "active_users": data.get('accounts_active', 0),
            "created_utc": data.get('created_utc', 0),
            "over_18": data.get('over18', False),
            "public_description": data.get('public_description', ''),
            "url": f"https://reddit.com/r/{subreddit}/",
            "icon_img": data.get('icon_img', ''),
            "banner_img": data.get('banner_img', ''),
            "community_icon": data.get('community_icon', ''),
            "restrict_posting": data.get('restrict_posting', False),
            "submit_text": data.get('submit_text', ''),
            "wiki_enabled": data.get('wiki_enabled', False),
            "accounts_active_is_fuzzed": data.get('accounts_active_is_fuzzed', False)
        })
        
    except Exception as e:
        return json.dumps({"error": f"Subreddit info lookup failed: {str(e)}"})

registry.register(
    name="reddit_search",
    toolset="reddit",
    schema={
        "name": "reddit_search", 
        "description": "Search Reddit for posts and comments using the Reddit API",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string"
                },
                "subreddit": {
                    "type": "string",
                    "description": "Optional subreddit to search in (e.g., 'python', 'technology')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (1-100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10
                },
                "sort": {
                    "type": "string",
                    "description": "Sort method: 'relevance', 'hot', 'top', 'new', 'comments'",
                    "enum": ["relevance", "hot", "top", "new", "comments"],
                    "default": "relevance"
                },
                "time_filter": {
                    "type": "string",
                    "description": "Time filter for 'top' sort: 'all', 'day', 'week', 'month', 'year', 'hour'",
                    "enum": ["all", "day", "week", "month", "year", "hour"],
                    "default": "all"
                }
            },
            "required": []
        }
    },
    handler=lambda args, **kw: reddit_search(
        query=args.get("query", ""),
        subreddit=args.get("subreddit"),
        limit=args.get("limit", 10),
        sort=args.get("sort", "relevance"),
        time_filter=args.get("time_filter", "all")
    ),
    check_fn=check_requirements,
    requires_env=["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"],
)

registry.register(
    name="reddit_subreddit_info",
    toolset="reddit",
    schema={
        "name": "reddit_subreddit_info", 
        "description": "Get information about a subreddit",
        "parameters": {
            "type": "object",
            "properties": {
                "subreddit": {
                    "type": "string",
                    "description": "Subreddit name"
                }
            },
            "required": ["subreddit"]
        }
    },
    handler=lambda args, **kw: reddit_subreddit_info(
        subreddit=args.get("subreddit", "")
    ),
    check_fn=check_requirements,
    requires_env=["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"],
)