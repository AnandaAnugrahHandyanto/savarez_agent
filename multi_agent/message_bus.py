#!/usr/bin/env python3
"""
Message Bus - Inter-Agent Communication

Provides message passing between sub-agents within a team with support for:
- Synchronous and asynchronous messaging
- Message attachments (files, data)
- Pub/sub patterns for team-wide broadcasts
- Direct agent-to-agent messages

The message bus enables coordination patterns like:
- Sharing intermediate results
- Requesting help from specialized agents
- Broadcasting status updates
- Synchronizing barriers
"""

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages that can be sent between agents."""
    # Direct messages
    DIRECT = "direct"           # Direct message to specific agent
    BROADCAST = "broadcast"     # Message to all agents
    MULTICAST = "multicast"     # Message to subset of agents
    
    # Coordination
    REQUEST = "request"         # Request for information/action
    RESPONSE = "response"       # Response to a request
    ACK = "ack"                 # Acknowledgment
    
    # Status updates
    STATUS_UPDATE = "status_update"  # Agent status change
    PROGRESS = "progress"       # Progress update
    ERROR = "error"             # Error notification
    
    # Team coordination
    BARRIER = "barrier"         # Barrier synchronization
    RESULT_AVAILABLE = "result_available"  # A result is ready
    
    # System
    SYSTEM = "system"           # System-level message


@dataclass
class Attachment:
    """
    An attachment to a message, such as a file or data blob.
    """
    name: str
    content: Any
    mime_type: str = "application/octet-stream"
    size: Optional[int] = None
    
    def __post_init__(self):
        if self.size is None and hasattr(self.content, '__len__'):
            try:
                self.size = len(self.content)
            except Exception:
                pass


@dataclass
class Message:
    """
    A message sent between agents in a team.
    
    Messages can be:
    - Direct: addressed to a specific agent
    - Broadcast: sent to all agents
    - Request/Response: paired communication
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    msg_type: MessageType = MessageType.DIRECT
    
    # Addressing
    sender_id: str = ""           # Agent ID of sender
    target_id: str = ""           # Agent ID of target (empty for broadcast)
    target_role: str = ""         # Alternative: target by role (e.g., "researcher")
    
    # Content
    subject: str = ""
    content: Any = None
    attachments: List[Attachment] = field(default_factory=list)
    
    # Threading/reply
    reply_to: Optional[str] = None  # message_id this is a reply to
    correlation_id: Optional[str] = None  # For grouping related messages
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: Optional[float] = None    # Time to live in seconds
    
    # Priority (higher = more urgent)
    priority: int = 0
    
    @property
    def is_broadcast(self) -> bool:
        return self.msg_type == MessageType.BROADCAST
    
    @property
    def is_direct(self) -> bool:
        return self.msg_type == MessageType.DIRECT and bool(self.target_id)
    
    @property
    def is_reply(self) -> bool:
        return self.reply_to is not None


@dataclass
class Subscription:
    """A subscription to messages matching certain criteria."""
    subscriber_id: str
    filter_fn: Callable[[Message], bool]
    callback: Callable[[Message], None]
    queue: Optional[asyncio.Queue] = None  # For async consumers


class MessageBus:
    """
    Inter-agent message bus for team communication.
    
    Supports:
    - Sync and async message delivery
    - Pub/sub filtering
    - Request/response patterns
    - Message persistence
    - Barrier synchronization
    """
    
    def __init__(self, team_id: str = ""):
        """
        Initialize the MessageBus.
        
        Args:
            team_id: The team this message bus belongs to
        """
        self.team_id = team_id
        self._running = False
        
        # Message queues and subscriptions
        self._subscribers: Dict[str, List[Subscription]] = defaultdict(list)
        self._subscriber_lock = threading.RLock()
        
        # In-flight requests waiting for responses
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_lock = threading.Lock()
        
        # Barrier synchronization
        self._barriers: Dict[str, asyncio.Barrier] = {}
        self._barrier_participants: Dict[str, set] = defaultdict(set)
        
        # Message history (optional, for debugging)
        self._message_history: List[Message] = []
        self._history_max = 1000
        
        # Async support
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_subscribers: List[Subscription] = []
    
    async def start(self) -> None:
        """Start the message bus."""
        self._running = True
        self._loop = asyncio.get_event_loop()
        logger.info(f"MessageBus for team {self.team_id} started")
    
    async def stop(self) -> None:
        """Stop the message bus."""
        self._running = False
        
        # Cancel all pending requests
        with self._request_lock:
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()
        
        # Clear barriers
        self._barriers.clear()
        self._barrier_participants.clear()
        
        logger.info(f"MessageBus for team {self.team_id} stopped")
    
    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[Message], None],
        filter_fn: Optional[Callable[[Message], bool]] = None,
    ) -> Subscription:
        """
        Subscribe to messages.
        
        Args:
            subscriber_id: ID of the subscribing agent
            callback: Function to call when matching message arrives
            filter_fn: Optional filter function
            
        Returns:
            Subscription object
        """
        if filter_fn is None:
            filter_fn = lambda msg: True
        
        sub = Subscription(
            subscriber_id=subscriber_id,
            filter_fn=filter_fn,
            callback=callback,
        )
        
        with self._subscriber_lock:
            self._subscribers[subscriber_id].append(sub)
        
        return sub
    
    def unsubscribe(self, subscriber_id: str, subscription: Subscription) -> None:
        """Unsubscribe from messages."""
        with self._subscriber_lock:
            if subscriber_id in self._subscribers:
                try:
                    self._subscribers[subscriber_id].remove(subscription)
                except ValueError:
                    pass
    
    async def subscribe_async(
        self,
        subscriber_id: str,
        filter_fn: Optional[Callable[[Message], bool]] = None,
    ) -> asyncio.Queue:
        """
        Subscribe with an async queue for message delivery.
        
        Returns an asyncio.Queue that receives matching messages.
        """
        if filter_fn is None:
            filter_fn = lambda msg: True
        
        queue = asyncio.Queue()
        
        async def async_callback(msg: Message):
            await queue.put(msg)
        
        sub = Subscription(
            subscriber_id=subscriber_id,
            filter_fn=filter_fn,
            callback=async_callback,
            queue=queue,
        )
        
        with self._subscriber_lock:
            self._async_subscribers.append(sub)
        
        return queue
    
    def send(self, message: Message) -> None:
        """
        Send a message synchronously.
        
        Args:
            message: The Message to send
        """
        self._deliver_message(message)
    
    async def send_async(self, message: Message) -> None:
        """
        Send a message asynchronously.
        
        Args:
            message: The Message to send
        """
        self._deliver_message(message)
    
    def _deliver_message(self, message: Message) -> None:
        """Deliver a message to matching subscribers."""
        # Store in history
        self._add_to_history(message)
        
        # Deliver to sync subscribers
        with self._subscriber_lock:
            for subscriber_id, subs in self._subscribers.items():
                # Don't deliver to sender unless it's a broadcast
                if subscriber_id == message.sender_id and not message.is_broadcast:
                    continue
                
                for sub in subs:
                    try:
                        if sub.filter_fn(message):
                            sub.callback(message)
                    except Exception as e:
                        logger.error(f"Subscriber callback error: {e}")
            
            # Deliver to async subscribers
            for sub in self._async_subscribers:
                if sub.subscriber_id == message.sender_id and not message.is_broadcast:
                    continue
                try:
                    if sub.filter_fn(message):
                        sub.callback(message)
                except Exception as e:
                    logger.error(f"Async subscriber callback error: {e}")
    
    def _add_to_history(self, message: Message) -> None:
        """Add message to history (with size limit)."""
        self._message_history.append(message)
        if len(self._message_history) > self._history_max:
            self._message_history = self._message_history[-self._history_max:]
    
    async def request(
        self,
        requester_id: str,
        subject: str,
        content: Any = None,
        target_id: str = "",
        target_role: str = "",
        timeout: float = 60.0,
    ) -> Message:
        """
        Send a request and wait for a response.
        
        Args:
            requester_id: ID of the requesting agent
            subject: Request subject
            content: Request content
            target_id: Specific agent to request from
            target_role: Request from agent with this role
            timeout: Seconds to wait for response
            
        Returns:
            Response Message
            
        Raises:
            TimeoutError: If no response received within timeout
        """
        request = Message(
            msg_type=MessageType.REQUEST,
            sender_id=requester_id,
            target_id=target_id,
            target_role=target_role,
            subject=subject,
            content=content,
            correlation_id=request.message_id,
        )
        
        # Create future to wait for response
        future: asyncio.Future = self._loop.create_future()
        
        # Register pending request
        with self._request_lock:
            self._pending_requests[request.message_id] = future
        
        # Subscribe to responses
        def response_filter(msg: Message) -> bool:
            return msg.reply_to == request.message_id
        
        def response_callback(msg: Message):
            if not future.done():
                future.set_result(msg)
        
        sub = self.subscribe(
            subscriber_id=requester_id,
            callback=response_callback,
            filter_fn=response_filter,
        )
        
        try:
            # Send the request
            self.send(request)
            
            # Wait for response
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                return response
            except asyncio.TimeoutError:
                raise TimeoutError(f"Request {subject} timed out after {timeout}s")
        
        finally:
            # Cleanup
            self.unsubscribe(requester_id, sub)
            with self._request_lock:
                self._pending_requests.pop(request.message_id, None)
    
    def reply_to(self, original: Message, content: Any, **kwargs) -> Message:
        """
        Create a reply message to a received message.
        
        Args:
            original: The original message to reply to
            content: Reply content
            **kwargs: Additional message fields
            
        Returns:
            A new Message that is a reply to the original
        """
        return Message(
            msg_type=MessageType.RESPONSE,
            sender_id=kwargs.get("sender_id", ""),
            target_id=original.sender_id,
            reply_to=original.message_id,
            correlation_id=original.correlation_id,
            content=content,
            subject=f"Re: {original.subject}" if original.subject else "",
        )
    
    def broadcast(
        self,
        sender_id: str,
        subject: str,
        content: Any = None,
        attachments: Optional[List[Attachment]] = None,
    ) -> Message:
        """
        Broadcast a message to all agents.
        
        Args:
            sender_id: ID of broadcasting agent
            subject: Message subject
            content: Message content
            attachments: Optional attachments
            
        Returns:
            The broadcast Message
        """
        message = Message(
            msg_type=MessageType.BROADCAST,
            sender_id=sender_id,
            subject=subject,
            content=content,
            attachments=attachments or [],
        )
        self.send(message)
        return message
    
    async def create_barrier(self, barrier_id: str, participants: int) -> Any:
        """
        Create a synchronization barrier.
        
        Args:
            barrier_id: Unique identifier for the barrier
            participants: Number of agents that must arrive
            
        Returns:
            A Barrier-like object
        """
        from threading import Barrier
        barrier = Barrier(participants)
        self._barriers[barrier_id] = barrier
        self._barrier_participants[barrier_id] = set()
        return barrier
    
    async def wait_at_barrier(self, barrier_id: str, agent_id: str) -> None:
        """
        Wait at a barrier.
        
        Args:
            barrier_id: The barrier to wait at
            agent_id: The agent waiting
            
        Raises:
            ValueError: If barrier doesn't exist
        """
        if barrier_id not in self._barriers:
            raise ValueError(f"Barrier {barrier_id} does not exist")
        
        self._barrier_participants[barrier_id].add(agent_id)
        
        try:
            await self._barriers[barrier_id].wait()
        except Exception as e:
            logger.error(f"Barrier wait error: {e}")
            raise
    
    def get_message_history(
        self,
        sender_id: Optional[str] = None,
        target_id: Optional[str] = None,
        msg_type: Optional[MessageType] = None,
        limit: int = 100,
    ) -> List[Message]:
        """
        Get message history with optional filtering.
        
        Args:
            sender_id: Filter by sender
            target_id: Filter by target
            msg_type: Filter by message type
            limit: Maximum messages to return
            
        Returns:
            List of matching Messages
        """
        results = self._message_history
        
        if sender_id:
            results = [m for m in results if m.sender_id == sender_id]
        if target_id:
            results = [m for m in results if m.target_id == target_id]
        if msg_type:
            results = [m for m in results if m.msg_type == msg_type]
        
        return results[-limit:]
    
    def get_bus_status(self) -> Dict[str, Any]:
        """Get current message bus status."""
        return {
            "team_id": self.team_id,
            "running": self._running,
            "history_size": len(self._message_history),
            "active_subscriptions": sum(len(s) for s in self._subscribers.values()),
            "pending_requests": len(self._pending_requests),
            "active_barriers": len(self._barriers),
        }
