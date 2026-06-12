/**
 * Shared icon registry — single source of truth for sidebar icon customization.
 * Imported by both SidebarReorder (settings picker) and App.tsx (sidebar rendering).
 */

import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  Calendar,
  Clock,
  Code,
  Compass,
  Cpu,
  Database,
  Download,
  Eye,
  FileText,
  Flame,
  FolderOpen,
  Globe,
  Heart,
  KeyRound,
  Layers,
  Lock,
  MessageSquare,
  Package,
  Plug,
  Puzzle,
  Radio,
  RotateCw,
  Search,
  Server,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Terminal,
  Users,
  Webhook,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";

export const ICON_REGISTRY: Record<string, LucideIcon> = {
  Activity, BarChart3, Bell, BookOpen, Calendar, Clock,
  Code, Compass, Cpu, Database, Download, Eye, FileText,
  Flame, FolderOpen, Globe, Heart, KeyRound, Layers, Lock,
  MessageSquare, Package, Plug, Puzzle, Radio, RotateCw,
  Search, Server, Settings, Shield, ShieldCheck, Sparkles,
  Star, Target, Terminal, Users, Webhook, Wrench, Zap,
};

export const ICON_NAMES = Object.keys(ICON_REGISTRY);
