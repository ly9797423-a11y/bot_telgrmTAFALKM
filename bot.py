#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                    بوت الحارس الذكي لحماية القنوات - النسخة العملاقة المتكاملة
#                                        Smart Guardian Channel Protection Bot
#                                             Version: 19.0.0 | Build: 2025
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

import asyncio
import logging
import json
import os
import re
import pickle
import secrets
import time
import traceback
import sys
import shutil
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from functools import wraps
from collections import defaultdict, deque

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters,
    ChatMemberHandler
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           إعدادات النظام المركزية
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class GuardianConfig:
    """إعدادات النظام المركزية"""
    
    BOT_TOKEN: str = "8682323172:AAFYWlT7EQQmCBjQVk4BzBSdnVCXK1lR07A"
    BOT_USERNAME: str = "protGebot"
    
    MASTER_ADMIN_ID: int = 6130994941
    MASTER_ADMIN_USERNAME: str = "Allawi04"
    
    FREE_CHANNELS_LIMIT: int = 2
    VIP_CHANNELS_LIMIT: int = 10
    FREE_TRIAL_DAYS: int = 14
    VIP_DURATION_DAYS: int = 30
    DEFAULT_VIP_PRICE: int = 5000
    
    FUNDING_PRICE_PER_MEMBER: int = 20
    SUBSCRIBE_REWARD_AMOUNT: int = 25
    INVITER_REWARD_AMOUNT: int = 150
    INVITED_REWARD_AMOUNT: int = 50
    
    DATABASE_FILE: str = "guardian_database.pkl"
    SETTINGS_FILE: str = "guardian_settings.json"
    BACKUP_FOLDER: str = "guardian_backups"
    TEMP_FOLDER: str = "guardian_temp"
    LOG_FOLDER: str = "guardian_logs"
    QR_FOLDER: str = "guardian_qrcodes"
    
    CHANNELS_PER_PAGE: int = 5
    AUTO_BAN_DAYS: int = 1000

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           نظام التسجيل
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def setup_logging():
    """إعداد نظام التسجيل"""
    os.makedirs(GuardianConfig.LOG_FOLDER, exist_ok=True)
    
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler(f"{GuardianConfig.LOG_FOLDER}/guardian.log", encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    return logging.getLogger('GuardianBot')

logger = setup_logging()

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           نظام قاعدة البيانات
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class MegaDatabase:
    """نظام قاعدة البيانات - متوافق مع البيانات الحالية"""
    
    def __init__(self):
        self._members: Dict[int, dict] = {}
        self._protected_channels: Dict[str, dict] = {}
        self._vip_members: Dict[int, datetime] = {}
        self._settings: Dict[str, Any] = {}
        self._active_campaigns: Dict[str, dict] = {}
        self._pending_campaigns: Dict[str, dict] = {}
        self._campaign_index: Dict[str, dict] = {}
        self._campaign_stats: Dict[str, dict] = {}
        self._gift_codes: Dict[str, dict] = {}
        self._used_gifts: Dict[int, List[str]] = {}
        self._activity_history: List[dict] = []
        self._mandatory_channels_config: Dict[str, dict] = {}
        self._admin_list: Set[int] = {GuardianConfig.MASTER_ADMIN_ID}
        
        # بيانات جديدة للخدمات والأقسام
        self._service_categories: Dict[str, dict] = {}
        self._services: Dict[str, dict] = {}
        self._service_orders: Dict[str, dict] = {}
        self._custom_button_names: Dict[str, str] = {}
        self._weekly_referral_winners: Dict[str, List[int]] = {}
        
        self._load_settings()
        self._load_database()
        self._ensure_master_exists()
        self._rebuild_indexes()
        self._init_default_button_names()
        
    def _init_default_button_names(self):
        """تهيئة أسماء الأزرار الافتراضية"""
        defaults = {
            'menu_services': '⚡ الخدمات',
            'menu_protection_system': '🛡 نظام الحماية',
            'menu_add_channel': '➕ إضافة قناة',
            'menu_delete_channel': '🗑 حذف قناة',
            'menu_my_channels': '📋 قنواتي',
            'menu_exchange': '🔄 تبادل اشتراك والربح',
            'menu_funding': '💰 تمويل اعضاء',
            'menu_referral': '🔗 دعوة صديق',
            'menu_vip': '⭐ اشتراك VIP',
            'menu_support': '💬 تواصل مع الدعم',
            'menu_admin': '🎛 لوحة التحكم',
            'menu_account_info': 'ℹ️ معلومات حسابك'
        }
        for key, value in defaults.items():
            if key not in self._custom_button_names:
                self._custom_button_names[key] = value
        
    def _ensure_master_exists(self):
        """التأكد من وجود حساب المدير"""
        master_id = GuardianConfig.MASTER_ADMIN_ID
        
        if master_id not in self._members:
            self._members[master_id] = {
                'member_id': master_id,
                'username': GuardianConfig.MASTER_ADMIN_USERNAME,
                'display_name': 'المدير',
                'balance': 0,
                'first_seen': datetime.now(),
                'joined_date': datetime.now(),
                'protected_channels': [],
                'last_active': datetime.now(),
                'referred_by': None,
                'referred_members': [],
                'referral_earnings': 0,
                'is_blocked': False,
                'block_reason': '',
                'referral_claimed': False,
                'completed_campaigns': [],
                'campaign_earnings': 0,
                'pending_verifications': {}
            }
            self._save_database()
            logger.info("✅ تم إنشاء حساب المدير")
            
    def _rebuild_indexes(self):
        """إعادة بناء الفهارس"""
        self._campaign_index.clear()
        
        for campaign_id, campaign in self._active_campaigns.items():
            if campaign.get('status') == 'active':
                channel_id = campaign.get('channel_id', '')
                channel_username = campaign.get('channel_username', '')
                key = channel_id if channel_id else channel_username
                
                if key:
                    self._campaign_index[key] = {
                        'campaign_id': campaign_id,
                        'channel_id': channel_id,
                        'channel_username': channel_username,
                        'channel_link': campaign.get('channel_link', ''),
                        'channel_title': campaign.get('channel_title', ''),
                        'owner_id': campaign.get('owner_id'),
                        'members_required': campaign.get('members_required', 0),
                        'members_joined': campaign.get('members_joined', 0),
                        'members_remaining': campaign.get('members_remaining', 0),
                        'completed_by': campaign.get('completed_by', []),
                        'reward': campaign.get('reward_per_subscriber', self._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT))
                    }
        
    def _load_settings(self):
        """تحميل الإعدادات"""
        default_settings = {
            "vip_price": GuardianConfig.DEFAULT_VIP_PRICE,
            "free_trial_days": GuardianConfig.FREE_TRIAL_DAYS,
            "maintenance_mode": False,
            "mandatory_channels": [],
            "funding_price_per_member": GuardianConfig.FUNDING_PRICE_PER_MEMBER,
            "subscribe_reward": GuardianConfig.SUBSCRIBE_REWARD_AMOUNT,
            "inviter_reward": GuardianConfig.INVITER_REWARD_AMOUNT,
            "invited_reward": GuardianConfig.INVITED_REWARD_AMOUNT,
            "admin_list": [GuardianConfig.MASTER_ADMIN_ID],
            "mandatory_channels_config": {},
            "service_categories": {},
            "services": {},
            "service_orders": {},
            "custom_button_names": {},
            "weekly_referral_winners": {}
        }
        
        try:
            if os.path.exists(GuardianConfig.SETTINGS_FILE):
                with open(GuardianConfig.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
        except:
            pass
            
        self._settings = default_settings
        self._mandatory_channels_config = self._settings.get('mandatory_channels_config', {})
        self._admin_list = set(self._settings.get('admin_list', [GuardianConfig.MASTER_ADMIN_ID]))
        
        # تحميل بيانات الخدمات من settings فقط
        self._service_categories = self._settings.get('service_categories', {})
        self._services = self._settings.get('services', {})
        self._service_orders = self._settings.get('service_orders', {})
        self._custom_button_names = self._settings.get('custom_button_names', {})
        self._weekly_referral_winners = self._settings.get('weekly_referral_winners', {})
        
    def _save_settings(self):
        """حفظ الإعدادات"""
        try:
            self._settings['mandatory_channels_config'] = self._mandatory_channels_config
            self._settings['admin_list'] = list(self._admin_list)
            self._settings['service_categories'] = self._service_categories
            self._settings['services'] = self._services
            self._settings['service_orders'] = self._service_orders
            self._settings['custom_button_names'] = self._custom_button_names
            self._settings['weekly_referral_winners'] = self._weekly_referral_winners
            with open(GuardianConfig.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2, default=str)
        except:
            pass
            
    def _load_database(self):
        """تحميل قاعدة البيانات"""
        try:
            if os.path.exists(GuardianConfig.DATABASE_FILE):
                with open(GuardianConfig.DATABASE_FILE, 'rb') as f:
                    data = pickle.load(f)
                    self._members = data.get('members', {})
                    self._protected_channels = data.get('protected_channels', {})
                    self._vip_members = data.get('vip_members', {})
                    self._activity_history = data.get('activity_history', [])
                    self._active_campaigns = data.get('active_campaigns', {})
                    self._pending_campaigns = data.get('pending_campaigns', {})
                    self._campaign_stats = data.get('campaign_stats', {})
                    self._gift_codes = data.get('gift_codes', {})
                    self._used_gifts = data.get('used_gifts', {})
                    logger.info(f"✅ تم تحميل البيانات: {len(self._members)} عضو")
        except Exception as e:
            logger.error(f"❌ خطأ في تحميل البيانات: {e}")
            
    def _save_database(self):
        """حفظ قاعدة البيانات"""
        try:
            data = {
                'members': self._members,
                'protected_channels': self._protected_channels,
                'vip_members': self._vip_members,
                'activity_history': self._activity_history,
                'active_campaigns': self._active_campaigns,
                'pending_campaigns': self._pending_campaigns,
                'campaign_stats': self._campaign_stats,
                'gift_codes': self._gift_codes,
                'used_gifts': self._used_gifts
            }
            
            if os.path.exists(GuardianConfig.DATABASE_FILE):
                os.makedirs(GuardianConfig.BACKUP_FOLDER, exist_ok=True)
                backup_path = f"{GuardianConfig.BACKUP_FOLDER}/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
                shutil.copy2(GuardianConfig.DATABASE_FILE, backup_path)
                
                backups = sorted([f for f in os.listdir(GuardianConfig.BACKUP_FOLDER) if f.startswith('backup_')])
                if len(backups) > 30:
                    for old in backups[:-30]:
                        os.remove(os.path.join(GuardianConfig.BACKUP_FOLDER, old))
                
            with open(GuardianConfig.DATABASE_FILE, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ البيانات: {e}")
            
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال الأعضاء والمشرفين
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_member(self, member_id: int) -> dict:
        """الحصول على بيانات العضو"""
        member_id = int(member_id)
        if member_id not in self._members:
            self._members[member_id] = {
                'member_id': member_id,
                'username': '',
                'display_name': '',
                'balance': 0,
                'first_seen': datetime.now(),
                'joined_date': datetime.now(),
                'protected_channels': [],
                'last_active': datetime.now(),
                'referred_by': None,
                'referred_members': [],
                'referral_earnings': 0,
                'is_blocked': False,
                'block_reason': '',
                'referral_claimed': False,
                'completed_campaigns': [],
                'campaign_earnings': 0,
                'pending_verifications': {}
            }
            self._save_database()
        return self._members[member_id]
    
    def update_member_info(self, member_id: int, user_obj):
        """تحديث معلومات العضو"""
        member = self.get_member(member_id)
        member['username'] = user_obj.username or ''
        member['display_name'] = user_obj.first_name or ''
        member['last_active'] = datetime.now()
        self._save_database()
        
    def is_admin(self, member_id: int) -> bool:
        """التحقق من صلاحيات المشرف"""
        return member_id in self._admin_list
    
    def promote_admin(self, target_id: int) -> bool:
        """رفع مشرف جديد"""
        self._admin_list.add(target_id)
        self._save_settings()
        self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"👑 رفع العضو {target_id} كمشرف")
        return True
    
    def demote_admin(self, target_id: int) -> bool:
        """حذف مشرف"""
        if target_id == GuardianConfig.MASTER_ADMIN_ID:
            return False
        self._admin_list.discard(target_id)
        self._save_settings()
        self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"⬇️ إزالة العضو {target_id} من المشرفين")
        return True
        
    def is_member_blocked(self, member_id: int) -> bool:
        """التحقق من حظر العضو"""
        member = self.get_member(member_id)
        return member.get('is_blocked', False)
        
    def block_member(self, member_id: int, reason: str = "") -> bool:
        """حظر عضو"""
        member = self.get_member(member_id)
        member['is_blocked'] = True
        member['block_reason'] = reason
        self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"🚫 تم حظر العضو {member_id}. السبب: {reason}")
        self._save_database()
        return True
        
    def unblock_member(self, member_id: int) -> bool:
        """فك حظر عضو"""
        member = self.get_member(member_id)
        member['is_blocked'] = False
        member['block_reason'] = ''
        self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"✅ تم فك الحظر عن العضو {member_id}")
        self._save_database()
        return True
        
    def delete_member(self, member_id: int) -> bool:
        """حذف عضو"""
        if member_id == GuardianConfig.MASTER_ADMIN_ID:
            return False
            
        if member_id in self._members:
            del self._members[member_id]
            
        channels_to_delete = []
        for ch_id, ch_data in self._protected_channels.items():
            if ch_data.get('owner_id') == member_id:
                channels_to_delete.append(ch_id)
        for ch_id in channels_to_delete:
            del self._protected_channels[ch_id]
            
        if member_id in self._vip_members:
            del self._vip_members[member_id]
            
        for cid, camp in list(self._active_campaigns.items()):
            if camp.get('owner_id') == member_id:
                self.cancel_campaign(cid, "تم حذف العضو")
                
        self._admin_list.discard(member_id)
        self._save_settings()
        
        self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"🗑 تم حذف العضو {member_id} من قاعدة البيانات")
        self._save_database()
        return True
        
    def get_blocked_members(self) -> List[dict]:
        """الحصول على الأعضاء المحظورين"""
        return [m for m in self._members.values() if m.get('is_blocked', False)]
        
    def search_member(self, member_id: int) -> Optional[dict]:
        """البحث عن عضو"""
        if member_id in self._members:
            return self._members[member_id]
        return None
        
    def get_top_balance_members(self, count: int = 10) -> List[dict]:
        """الحصول على أعلى الأعضاء رصيداً"""
        members = list(self._members.values())
        members.sort(key=lambda x: x.get('balance', 0), reverse=True)
        return members[:count]
    
    def get_top_referrers(self, count: int = 5) -> List[dict]:
        """الحصول على أفضل المشاركين بالإحالة"""
        members = list(self._members.values())
        members.sort(key=lambda x: len(x.get('referred_members', [])), reverse=True)
        return members[:count]
        
    def get_member_activity(self, member_id: int) -> List[dict]:
        """الحصول على سجل نشاطات عضو"""
        return [log for log in self._activity_history if log.get('member_id') == member_id]
    
    def get_active_members(self) -> List[int]:
        """الحصول على الأعضاء النشطين"""
        return list(self._members.keys())
        
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال الإحالة
    # ═══════════════════════════════════════════════════════════════════════════
    
    def process_referral(self, new_member_id: int, inviter_id: int) -> Tuple[bool, str]:
        """معالجة الإحالة"""
        if inviter_id == new_member_id:
            return False, "لا يمكنك دعوة نفسك"
            
        if inviter_id not in self._members:
            return False, "رابط الدعوة غير صالح"
            
        new_member = self.get_member(new_member_id)
        inviter = self.get_member(inviter_id)
        
        if new_member.get('referral_claimed', False):
            return False, "لقد حصلت على مكافأة الإحالة مسبقاً"
            
        inviter_reward = self._settings.get('inviter_reward', GuardianConfig.INVITER_REWARD_AMOUNT)
        invited_reward = self._settings.get('invited_reward', GuardianConfig.INVITED_REWARD_AMOUNT)
        
        inviter['balance'] = inviter.get('balance', 0) + inviter_reward
        inviter['referral_earnings'] = inviter.get('referral_earnings', 0) + inviter_reward
        
        if 'referred_members' not in inviter:
            inviter['referred_members'] = []
        if new_member_id not in inviter['referred_members']:
            inviter['referred_members'].append(new_member_id)
            
        new_member['balance'] = new_member.get('balance', 0) + invited_reward
        new_member['referred_by'] = inviter_id
        new_member['referral_claimed'] = True
        
        self._log_activity(inviter_id, f"حصل على {inviter_reward} IQD مكافأة إحالة")
        self._log_activity(new_member_id, f"حصل على {invited_reward} IQD مكافأة تسجيل")
        
        self._save_database()
        return True, "تمت معالجة الإحالة بنجاح"
        
    def get_referral_link(self, member_id: int) -> str:
        """إنشاء رابط الإحالة"""
        return f"https://t.me/{GuardianConfig.BOT_USERNAME}?start={member_id}"
        
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال الخدمات والأقسام - مع ضمان الحذف النهائي
    # ═══════════════════════════════════════════════════════════════════════════
    
    def create_service_category(self, name: str, description: str) -> str:
        """إنشاء قسم خدمات جديد"""
        cat_id = f"CAT_{int(time.time())}"
        self._service_categories[cat_id] = {
            'id': cat_id,
            'name': name,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'services': {}
        }
        self._save_settings()
        self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"📁 أنشأ قسم خدمات: {name}")
        return cat_id
    
    def add_service_to_category(self, category_id: str, name: str, description: str, 
                                price_per_1000: int, duration: str,
                                min_amount: int, max_amount: int) -> str:
        """إضافة خدمة إلى قسم"""
        srv_id = f"SRV_{int(time.time())}"
        service_data = {
            'id': srv_id,
            'name': name,
            'description': description,
            'category_id': category_id,
            'needs_link': True,
            'price_per_1000': price_per_1000,
            'duration': duration,
            'min_amount': min_amount,
            'max_amount': max_amount,
            'created_at': datetime.now().isoformat()
        }
        self._services[srv_id] = service_data
        
        if category_id in self._service_categories:
            if 'services' not in self._service_categories[category_id]:
                self._service_categories[category_id]['services'] = {}
            self._service_categories[category_id]['services'][srv_id] = service_data
        
        self._save_settings()
        self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"➕ أضاف خدمة: {name} إلى القسم {category_id}")
        return srv_id
    
    def delete_category(self, category_id: str) -> bool:
        """حذف قسم وجميع خدماته من كل مكان"""
        if category_id in self._service_categories:
            # حذف جميع الخدمات المرتبطة من self._services
            services_to_delete = list(self._service_categories[category_id].get('services', {}).keys())
            for srv_id in services_to_delete:
                if srv_id in self._services:
                    del self._services[srv_id]
            # حذف القسم من self._service_categories
            del self._service_categories[category_id]
            # حفظ الإعدادات
            self._save_settings()
            self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"🗑 حذف قسم خدمات: {category_id}")
            return True
        return False
    
    def delete_service(self, service_id: str) -> bool:
        """حذف خدمة من كل مكان"""
        if service_id in self._services:
            cat_id = self._services[service_id].get('category_id')
            # حذف من القسم
            if cat_id and cat_id in self._service_categories:
                if service_id in self._service_categories[cat_id].get('services', {}):
                    del self._service_categories[cat_id]['services'][service_id]
            # حذف من الخدمات
            del self._services[service_id]
            # حفظ
            self._save_settings()
            self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"🗑 حذف خدمة: {service_id}")
            return True
        return False
    
    def get_all_categories(self) -> List[dict]:
        """الحصول على جميع الأقسام"""
        return list(self._service_categories.values())
    
    def get_category_services(self, category_id: str) -> List[dict]:
        """الحصول على خدمات قسم"""
        if category_id in self._service_categories:
            services = []
            for srv_id in self._service_categories[category_id].get('services', {}):
                if srv_id in self._services:
                    services.append(self._services[srv_id])
            return services
        return []
    
    def create_service_order(self, user_id: int, service_id: str, quantity: int, link: str = "") -> str:
        """إنشاء طلب خدمة"""
        order_id = f"ORD_{int(time.time())}"
        service = self._services.get(service_id, {})
        price_per_1000 = service.get('price_per_1000', 0)
        total_cost = int((quantity / 1000) * price_per_1000)
        
        self._service_orders[order_id] = {
            'order_id': order_id,
            'user_id': user_id,
            'service_id': service_id,
            'service_name': service.get('name', ''),
            'category_id': service.get('category_id', ''),
            'quantity': quantity,
            'link': link,
            'total_cost': total_cost,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        self._save_settings()
        self._log_activity(user_id, f"📝 أنشأ طلب خدمة: {service.get('name', '')} - كمية: {quantity}")
        return order_id
    
    def get_pending_orders(self) -> List[dict]:
        """الحصول على الطلبات المعلقة"""
        return [o for o in self._service_orders.values() if o.get('status') == 'pending']
    
    def get_order(self, order_id: str) -> Optional[dict]:
        """الحصول على طلب"""
        return self._service_orders.get(order_id)
    
    def approve_order(self, order_id: str) -> bool:
        """الموافقة على طلب"""
        if order_id in self._service_orders:
            self._service_orders[order_id]['status'] = 'approved'
            self._save_settings()
            self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"✅ وافق على طلب: {order_id}")
            return True
        return False
    
    def reject_order(self, order_id: str) -> bool:
        """رفض طلب"""
        if order_id in self._service_orders:
            order = self._service_orders[order_id]
            self._service_orders[order_id]['status'] = 'rejected'
            self.add_balance(order['user_id'], order['total_cost'])
            self._save_settings()
            self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"❌ رفض طلب: {order_id}")
            return True
        return False
    
    def get_button_name(self, key: str) -> str:
        """الحصول على اسم الزر المخصص"""
        return self._custom_button_names.get(key, key)
    
    def set_button_name(self, key: str, name: str):
        """تعيين اسم الزر"""
        self._custom_button_names[key] = name
        self._save_settings()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال حملات التمويل
    # ═══════════════════════════════════════════════════════════════════════════
    
    def has_active_campaign_for_channel(self, owner_id: int, channel_username: str) -> bool:
        """التحقق من وجود حملة نشطة لنفس القناة"""
        for campaign in self._active_campaigns.values():
            if (campaign.get('owner_id') == owner_id and 
                campaign.get('channel_username', '').lower() == channel_username.lower() and
                campaign.get('status') in ['pending', 'active']):
                return True
        for campaign in self._pending_campaigns.values():
            if (campaign.get('owner_id') == owner_id and 
                campaign.get('channel_username', '').lower() == channel_username.lower()):
                return True
        return False
    
    def create_pending_campaign(self, owner_id: int, channel_id: str, channel_title: str,
                                channel_link: str, channel_username: str, members_count: int) -> Tuple[bool, Any]:
        """إنشاء حملة تمويل معلقة"""
        if self.has_active_campaign_for_channel(owner_id, channel_username):
            return False, "❌ لديك حملة تمويل نشطة بالفعل لهذه القناة. يرجى الانتظار حتى اكتمالها."
        
        price_per_member = self._settings.get('funding_price_per_member', GuardianConfig.FUNDING_PRICE_PER_MEMBER)
        total_cost = members_count * price_per_member
        
        campaign_id = f"CAMP_{int(time.time())}"
        
        if not channel_username and channel_link:
            if 't.me/' in channel_link:
                channel_username = channel_link.split('t.me/')[-1].split('/')[0]
            elif channel_link.startswith('@'):
                channel_username = channel_link.replace('@', '')
        
        if channel_link and not channel_link.startswith('http'):
            if channel_username:
                channel_link = f"https://t.me/{channel_username}"
        
        campaign = {
            'campaign_id': campaign_id,
            'owner_id': owner_id,
            'channel_id': channel_id,
            'channel_title': channel_title,
            'channel_link': channel_link,
            'channel_username': channel_username,
            'members_required': members_count,
            'members_joined': 0,
            'members_remaining': members_count,
            'price_per_member': price_per_member,
            'total_cost': total_cost,
            'status': 'pending',
            'is_approved': False,
            'approved_by': None,
            'approved_at': None,
            'created_at': datetime.now(),
            'completed_at': None,
            'completed_by': [],
            'is_reported': False,
            'report_reason': '',
            'reported_by': None,
            'reward_per_subscriber': self._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT)
        }
        
        self._pending_campaigns[campaign_id] = campaign
        self._log_activity(owner_id, f"أنشأ حملة تمويل: {channel_title} - {members_count} عضو")
        self._save_database()
        
        logger.info(f"📋 حملة معلقة: {campaign_id} | {channel_title}")
        return True, campaign
        
    def approve_campaign(self, campaign_id: str, admin_id: int) -> Tuple[bool, str, Optional[dict]]:
        """الموافقة على حملة"""
        if campaign_id not in self._pending_campaigns:
            return False, "الحملة غير موجودة", None
            
        campaign = self._pending_campaigns[campaign_id]
        
        campaign['status'] = 'active'
        campaign['is_approved'] = True
        campaign['approved_by'] = admin_id
        campaign['approved_at'] = datetime.now()
        
        self._active_campaigns[campaign_id] = campaign
        
        channel_id = campaign.get('channel_id', '')
        channel_username = campaign.get('channel_username', '')
        key = channel_id if channel_id else channel_username
        
        if key:
            self._campaign_index[key] = {
                'campaign_id': campaign_id,
                'channel_id': channel_id,
                'channel_username': channel_username,
                'channel_link': campaign.get('channel_link', ''),
                'channel_title': campaign.get('channel_title', ''),
                'owner_id': campaign.get('owner_id'),
                'members_required': campaign.get('members_required', 0),
                'members_joined': 0,
                'members_remaining': campaign.get('members_required', 0),
                'completed_by': [],
                'reward': campaign.get('reward_per_subscriber', self._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT))
            }
        
        del self._pending_campaigns[campaign_id]
        
        self._log_activity(admin_id, f"وافق على حملة {campaign.get('channel_title', '')}")
        self._save_database()
        
        return True, "تمت الموافقة على الحملة بنجاح", campaign
        
    def reject_campaign(self, campaign_id: str, admin_id: int, reason: str = "") -> Tuple[bool, str, Optional[dict]]:
        """رفض حملة"""
        if campaign_id not in self._pending_campaigns:
            return False, "الحملة غير موجودة", None
            
        campaign = self._pending_campaigns[campaign_id]
        owner_id = campaign['owner_id']
        total_cost = campaign['total_cost']
        
        owner = self.get_member(owner_id)
        owner['balance'] = owner.get('balance', 0) + total_cost
        
        campaign['status'] = 'rejected'
        campaign['rejected_by'] = admin_id
        campaign['rejected_at'] = datetime.now()
        campaign['reject_reason'] = reason
        
        self._active_campaigns[campaign_id] = campaign
        del self._pending_campaigns[campaign_id]
        
        self._log_activity(admin_id, f"رفض حملة {campaign.get('channel_title', '')}: {reason}")
        self._log_activity(owner_id, f"رفضت حملتك {campaign.get('channel_title', '')} وأعيد {total_cost} IQD")
        self._save_database()
        
        return True, "تم رفض الحملة وإعادة المبلغ", campaign
        
    def get_pending_campaigns(self) -> List[dict]:
        """الحصول على الحملات المعلقة"""
        return list(self._pending_campaigns.values())
        
    def get_campaign(self, campaign_id: str) -> Optional[dict]:
        """الحصول على حملة"""
        if campaign_id in self._active_campaigns:
            return self._active_campaigns[campaign_id]
        if campaign_id in self._pending_campaigns:
            return self._pending_campaigns[campaign_id]
        return None
        
    def get_active_campaigns(self) -> List[dict]:
        """الحصول على الحملات النشطة"""
        return [c for c in self._active_campaigns.values() if c.get('status') == 'active']
        
    def get_uncompleted_campaigns_for_member(self, member_id: int) -> List[dict]:
        """الحصول على الحملات غير المكتملة"""
        active = self.get_active_campaigns()
        uncompleted = []
        member = self.get_member(member_id)
        completed = member.get('completed_campaigns', [])
        
        for camp in active:
            if camp.get('owner_id') == member_id:
                continue
            campaign_id = camp.get('campaign_id', '')
            if campaign_id and campaign_id not in completed and member_id not in camp.get('completed_by', []):
                uncompleted.append(camp)
                
        return uncompleted
        
    def verify_member_subscriptions(self, member_id: int, campaign_ids: List[str], bot=None) -> Tuple[int, List[str]]:
        """التحقق من اشتراكات العضو وإعطاء المكافآت"""
        successful = []
        total_reward = 0
        member = self.get_member(member_id)
        
        for campaign_id in campaign_ids:
            campaign = self._active_campaigns.get(campaign_id)
            
            if not campaign or campaign.get('status') != 'active':
                continue
                
            if 'completed_campaigns' not in member:
                member['completed_campaigns'] = []
                
            if campaign_id in member.get('completed_campaigns', []) or member_id in campaign.get('completed_by', []):
                continue
                
            reward = campaign.get('reward_per_subscriber', self._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT))
            
            member['balance'] = member.get('balance', 0) + reward
            member['campaign_earnings'] = member.get('campaign_earnings', 0) + reward
            member['completed_campaigns'].append(campaign_id)
            
            if 'completed_by' not in campaign:
                campaign['completed_by'] = []
            campaign['completed_by'].append(member_id)
            
            campaign['members_joined'] = campaign.get('members_joined', 0) + 1
            if campaign.get('members_remaining', 0) > 0:
                campaign['members_remaining'] = campaign.get('members_remaining', 0) - 1
            
            channel_id = campaign.get('channel_id', '')
            channel_username = campaign.get('channel_username', '')
            key = channel_id if channel_id else channel_username
            
            if key and key in self._campaign_index:
                self._campaign_index[key]['members_joined'] = campaign['members_joined']
                self._campaign_index[key]['members_remaining'] = campaign['members_remaining']
            
            if campaign['members_remaining'] == 0:
                campaign['status'] = 'completed'
                campaign['completed_at'] = datetime.now()
                self._check_and_remove_mandatory_on_complete(campaign)
                
            total_reward += reward
            successful.append(campaign_id)
            self._log_activity(member_id, f"حصل على {reward} IQD من حملة {campaign.get('channel_title', '')}")
            
        if successful:
            self._save_database()
            
        return len(successful), successful
    
    def _check_and_remove_mandatory_on_complete(self, campaign: dict):
        """إزالة القناة من الاشتراك الإجباري عند اكتمال التمويل"""
        channel_link = campaign.get('channel_link', '')
        channel_username = campaign.get('channel_username', '')
        
        if channel_link:
            self._remove_mandatory_by_link(channel_link)
        if channel_username:
            self._remove_mandatory_by_link(f"https://t.me/{channel_username}")
            self._remove_mandatory_by_link(f"@{channel_username}")
    
    def _remove_mandatory_by_link(self, link: str):
        """إزالة قناة من الاشتراك الإجباري حسب الرابط"""
        channels = self._settings.get('mandatory_channels', [])
        if link in channels:
            channels.remove(link)
            self._settings['mandatory_channels'] = channels
            if link in self._mandatory_channels_config:
                del self._mandatory_channels_config[link]
            self._save_settings()
            self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"🔓 تم إزالة {link} من الاشتراك الإجباري (اكتمل التمويل)")
    
    def remove_mandatory_channel(self, channel: str) -> bool:
        """حذف قناة إجبارية بشكل نهائي من جميع الأماكن"""
        channels = self._settings.get('mandatory_channels', [])
        removed = False
        
        # البحث المباشر
        if channel in channels:
            channels.remove(channel)
            self._mandatory_channels_config.pop(channel, None)
            removed = True
        else:
            # البحث بكل الصيغ الممكنة
            to_remove = []
            for ch in channels:
                if channel in ch or ch in channel:
                    to_remove.append(ch)
            for ch in to_remove:
                channels.remove(ch)
                self._mandatory_channels_config.pop(ch, None)
                removed = True
        
        if removed:
            self._settings['mandatory_channels'] = channels
            self._save_settings()
            self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"🗑 حذف من الاشتراك الإجباري: {channel}")
        
        return removed
        
    def cancel_campaign(self, campaign_id: str, reason: str = "") -> bool:
        """إلغاء حملة"""
        if campaign_id in self._active_campaigns:
            campaign = self._active_campaigns[campaign_id]
            campaign['status'] = 'cancelled'
            campaign['cancelled_at'] = datetime.now()
            campaign['cancel_reason'] = reason
            
            channel_id = campaign.get('channel_id', '')
            channel_username = campaign.get('channel_username', '')
            key = channel_id if channel_id else channel_username
            if key in self._campaign_index:
                del self._campaign_index[key]
                
            self._log_activity(campaign['owner_id'], f"ألغيت حملة {campaign.get('channel_title', '')}")
            self._save_database()
            return True
        return False
    
    def cancel_all_campaigns_for_channel(self, channel_username_or_id: str, reason: str = "تم حذف البوت من القناة") -> List[int]:
        """إلغاء جميع حملات قناة معينة وإرجاع قائمة المالكين للإشعار"""
        owners = []
        for cid, camp in list(self._active_campaigns.items()):
            if (camp.get('channel_username') == channel_username_or_id or 
                camp.get('channel_id') == channel_username_or_id or
                channel_username_or_id in camp.get('channel_username', '') or
                camp.get('channel_username', '') in channel_username_or_id):
                if camp.get('status') in ['active', 'pending']:
                    camp['status'] = 'cancelled'
                    camp['cancelled_at'] = datetime.now()
                    camp['cancel_reason'] = reason
                    owners.append(camp['owner_id'])
        
        for cid, camp in list(self._pending_campaigns.items()):
            if (camp.get('channel_username') == channel_username_or_id or 
                camp.get('channel_id') == channel_username_or_id):
                camp['status'] = 'cancelled'
                camp['cancelled_at'] = datetime.now()
                camp['cancel_reason'] = reason
                owners.append(camp['owner_id'])
        
        self.remove_mandatory_channel(channel_username_or_id)
        
        if owners:
            self._save_database()
            self._save_settings()
        return list(set(owners))
        
    def report_campaign(self, campaign_id: str, reporter_id: int, reason: str) -> bool:
        """الإبلاغ عن حملة"""
        if campaign_id in self._active_campaigns:
            campaign = self._active_campaigns[campaign_id]
            campaign['is_reported'] = True
            campaign['report_reason'] = reason
            campaign['reported_by'] = reporter_id
            campaign['reported_at'] = datetime.now()
            self._log_activity(reporter_id, f"أبلغ عن حملة: {campaign.get('channel_title', '')}")
            self._save_database()
            return True
        return False
        
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال الهدايا
    # ═══════════════════════════════════════════════════════════════════════════
    
    def create_gift_code(self, admin_id: int, max_uses: int, amount: int) -> str:
        """إنشاء رمز هدية"""
        code = secrets.token_urlsafe(16)
        
        self._gift_codes[code] = {
            'code': code,
            'created_by': admin_id,
            'created_at': datetime.now(),
            'max_uses': max_uses,
            'used_count': 0,
            'amount': amount,
            'total_amount': max_uses * amount,
            'used_by': [],
            'is_active': True
        }
        self._log_activity(admin_id, f"أنشأ رمز هدية: {max_uses} استخدام، {amount} IQD")
        self._save_database()
        return code
        
    def redeem_gift_code(self, code: str, member_id: int) -> Tuple[bool, str]:
        """استخدام رمز الهدية"""
        code = code.strip()
        
        if code not in self._gift_codes:
            return False, "❌ رمز الهدية غير صالح"
            
        gift = self._gift_codes[code]
        
        if not gift.get('is_active', False):
            return False, "❌ انتهت صلاحية هذا الرمز"
            
        if gift['used_count'] >= gift['max_uses']:
            gift['is_active'] = False
            self._save_database()
            return False, "❌ اكتمل عدد المستخدمين المسموح بهم"
            
        if member_id not in self._used_gifts:
            self._used_gifts[member_id] = []
            
        if code in self._used_gifts[member_id]:
            return False, "❌ لقد استخدمت هذا الرمز مسبقاً"
            
        member = self.get_member(member_id)
        amount = gift['amount']
        
        member['balance'] = member.get('balance', 0) + amount
        
        gift['used_count'] = gift.get('used_count', 0) + 1
        if 'used_by' not in gift:
            gift['used_by'] = []
        gift['used_by'].append(member_id)
        
        self._used_gifts[member_id].append(code)
        
        if gift['used_count'] >= gift['max_uses']:
            gift['is_active'] = False
            self._log_activity(GuardianConfig.MASTER_ADMIN_ID, f"🎁 انتهى رابط الهدية {code} - اكتمل العدد")
            
        self._log_activity(member_id, f"حصل على {amount} IQD من هدية")
        self._save_database()
        
        return True, f"✅ تم إضافة {amount} IQD إلى رصيدك"
        
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال قنوات الحماية
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_member_channels(self, member_id: int) -> List[str]:
        """الحصول على قنوات العضو"""
        member = self.get_member(member_id)
        return member.get('protected_channels', [])
        
    def add_protected_channel(self, member_id: int, channel_id: str, channel_title: str = "") -> bool:
        """إضافة قناة حماية"""
        member = self.get_member(member_id)
        channels = member.get('protected_channels', [])
        
        if str(channel_id) not in channels:
            channels.append(str(channel_id))
            member['protected_channels'] = channels
            
        self._protected_channels[str(channel_id)] = {
            'owner_id': member_id,
            'title': channel_title,
            'added_date': datetime.now(),
            'protection_settings': {
                'block_new_members': False,
                'block_leaving_members': False,
                'block_no_username': False
            },
            'stats': {
                'total_blocked': 0,
                'total_joined': 0,
                'total_left': 0
            }
        }
        
        self._log_activity(member_id, f"➕ أضاف قناة حماية: {channel_title}")
        self._save_database()
        return True
        
    def remove_protected_channel(self, member_id: int, channel_id: str) -> bool:
        """حذف قناة حماية"""
        member = self.get_member(member_id)
        channels = member.get('protected_channels', [])
        
        if str(channel_id) in channels:
            channels.remove(str(channel_id))
            member['protected_channels'] = channels
            
        if str(channel_id) in self._protected_channels:
            channel_title = self._protected_channels[str(channel_id)].get('title', '')
            del self._protected_channels[str(channel_id)]
            self._log_activity(member_id, f"🗑 حذف قناة: {channel_title}")
            
        self._save_database()
        return True
        
    def get_channel_settings(self, channel_id: str) -> dict:
        """الحصول على إعدادات قناة"""
        if str(channel_id) in self._protected_channels:
            return self._protected_channels[str(channel_id)].get('protection_settings', {})
        return {}
        
    def toggle_channel_protection(self, channel_id: str, setting: str) -> bool:
        """تبديل إعداد حماية"""
        if str(channel_id) in self._protected_channels:
            settings = self._protected_channels[str(channel_id)].get('protection_settings', {})
            current = settings.get(setting, False)
            settings[setting] = not current
            
            action = "تفعيل" if not current else "تعطيل"
            owner_id = self._protected_channels[str(channel_id)]['owner_id']
            channel_title = self._protected_channels[str(channel_id)].get('title', '')
            
            setting_names = {
                'block_new_members': 'حظر المنضمين',
                'block_leaving_members': 'حظر المغادرين',
                'block_no_username': 'حظر بدون يوزر'
            }
            setting_name = setting_names.get(setting, setting)
            
            self._log_activity(owner_id, f"⚙️ {action} {setting_name} في {channel_title}")
            self._save_database()
            return not current
        return False
        
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال VIP
    # ═══════════════════════════════════════════════════════════════════════════
    
    def is_vip_member(self, member_id: int) -> bool:
        """التحقق من عضوية VIP"""
        member_id = int(member_id)
        if member_id == GuardianConfig.MASTER_ADMIN_ID:
            return True
            
        if member_id in self._vip_members:
            expiry = self._vip_members[member_id]
            if isinstance(expiry, str):
                expiry = datetime.fromisoformat(expiry)
            return datetime.now() < expiry
        return False
        
    def is_free_trial_valid(self, member_id: int) -> bool:
        """التحقق من الفترة التجريبية"""
        member_id = int(member_id)
        if member_id == GuardianConfig.MASTER_ADMIN_ID:
            return True
            
        member = self.get_member(member_id)
        first_seen = member['first_seen']
        if isinstance(first_seen, str):
            first_seen = datetime.fromisoformat(first_seen)
        free_days = self._settings.get('free_trial_days', GuardianConfig.FREE_TRIAL_DAYS)
        return datetime.now() < first_seen + timedelta(days=free_days)
        
    def can_use_bot(self, member_id: int) -> Tuple[bool, str]:
        """التحقق من إمكانية استخدام البوت"""
        member_id = int(member_id)
        
        if member_id == GuardianConfig.MASTER_ADMIN_ID:
            return True, "مدير النظام"
            
        if self.is_member_blocked(member_id):
            return False, "تم حظر حسابك"
            
        if self._settings.get('maintenance_mode', False):
            return False, "البوت تحت الصيانة"
            
        if self.is_vip_member(member_id):
            expiry = self._vip_members[member_id]
            if isinstance(expiry, str):
                expiry = datetime.fromisoformat(expiry)
            days_left = (expiry - datetime.now()).days
            return True, f"VIP - متبقي {days_left} يوم"
            
        if self.is_free_trial_valid(member_id):
            member = self.get_member(member_id)
            first_seen = member['first_seen']
            if isinstance(first_seen, str):
                first_seen = datetime.fromisoformat(first_seen)
            free_days = self._settings.get('free_trial_days', GuardianConfig.FREE_TRIAL_DAYS)
            days_passed = (datetime.now() - first_seen).days
            days_left = free_days - days_passed
            return True, f"تجريبي - متبقي {days_left} يوم"
            
        return False, "انتهت الفترة التجريبية"
        
    def get_max_channels(self, member_id: int) -> int:
        """الحصول على الحد الأقصى للقنوات"""
        if self.is_vip_member(member_id) or member_id == GuardianConfig.MASTER_ADMIN_ID:
            return GuardianConfig.VIP_CHANNELS_LIMIT
        return GuardianConfig.FREE_CHANNELS_LIMIT
        
    def add_balance(self, member_id: int, amount: int) -> int:
        """إضافة رصيد"""
        member = self.get_member(member_id)
        old_balance = member.get('balance', 0)
        member['balance'] = old_balance + amount
        self._log_activity(member_id, f"تم شحن {amount} IQD")
        self._save_database()
        return member['balance']
        
    def deduct_balance(self, member_id: int, amount: int) -> bool:
        """خصم من الرصيد"""
        member = self.get_member(member_id)
        if member.get('balance', 0) >= amount:
            member['balance'] -= amount
            self._save_database()
            return True
        return False
    
    def force_deduct_balance(self, member_id: int, amount: int) -> int:
        """خصم رصيد حتى لو كان أقل"""
        member = self.get_member(member_id)
        member['balance'] = member.get('balance', 0) - amount
        self._save_database()
        return member['balance']
        
    def subscribe_vip(self, member_id: int) -> Tuple[bool, str]:
        """الاشتراك في VIP"""
        price = self._settings.get('vip_price', GuardianConfig.DEFAULT_VIP_PRICE)
        
        if self.deduct_balance(member_id, price):
            expiry = datetime.now() + timedelta(days=GuardianConfig.VIP_DURATION_DAYS)
            self._vip_members[member_id] = expiry
            self._log_activity(member_id, f"⭐ اشترك في VIP")
            self._save_database()
            return True, f"✅ تم الاشتراك VIP بنجاح"
        else:
            return False, f"❌ رصيدك غير كافي. المطلوب {price} IQD"
            
    def get_vip_expiry_date(self, member_id: int) -> Optional[datetime]:
        """الحصول على تاريخ انتهاء VIP"""
        if member_id in self._vip_members:
            expiry = self._vip_members[member_id]
            if isinstance(expiry, str):
                return datetime.fromisoformat(expiry)
            return expiry
        return None
        
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال الإحصائيات
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_system_stats(self) -> dict:
        """الحصول على إحصائيات النظام"""
        now = datetime.now()
        
        active_vip = 0
        for mid, exp in self._vip_members.items():
            exp_date = exp if isinstance(exp, datetime) else datetime.fromisoformat(exp)
            if exp_date > now:
                active_vip += 1
                
        return {
            'total_members': len(self._members),
            'total_protected_channels': len(self._protected_channels),
            'total_campaigns': len(self._active_campaigns),
            'active_vip': active_vip,
            'blocked_members': len(self.get_blocked_members()),
            'admin_count': len(self._admin_list),
            'total_balance': sum(m.get('balance', 0) for m in self._members.values()),
            'pending_campaigns': len(self._pending_campaigns),
            'active_campaigns_count': len([c for c in self._active_campaigns.values() if c.get('status') == 'active']),
            'completed_campaigns': len([c for c in self._active_campaigns.values() if c.get('status') == 'completed']),
            'active_gifts': len([g for g in self._gift_codes.values() if g.get('is_active', False)]),
            'total_categories': len(self._service_categories),
            'total_services': len(self._services),
            'pending_orders': len(self.get_pending_orders())
        }
        
    def get_recent_members(self, count: int = 20) -> List[dict]:
        """الحصول على أحدث الأعضاء"""
        members = list(self._members.values())
        members.sort(key=lambda x: x.get('joined_date', datetime.now()) if isinstance(x.get('joined_date'), datetime) else datetime.now(), reverse=True)
        return members[:count]
        
    def get_all_vip_members(self) -> List[Tuple[int, datetime]]:
        """الحصول على أعضاء VIP"""
        result = []
        for mid, exp in self._vip_members.items():
            exp_date = exp if isinstance(exp, datetime) else datetime.fromisoformat(exp)
            result.append((mid, exp_date))
        return result
        
    def _log_activity(self, member_id: int, action: str):
        """تسجيل نشاط"""
        self._activity_history.append({
            'member_id': member_id,
            'action': action,
            'timestamp': datetime.now()
        })
        if len(self._activity_history) > 5000:
            self._activity_history = self._activity_history[-5000:]
        self._save_database()
        
    def check_expired_vip(self) -> List[int]:
        """فحص انتهاء VIP"""
        expired = []
        now = datetime.now()
        
        for mid, exp in list(self._vip_members.items()):
            exp_date = exp if isinstance(exp, datetime) else datetime.fromisoformat(exp)
            if exp_date < now:
                del self._vip_members[mid]
                expired.append(mid)
                self._log_activity(mid, "انتهاء اشتراك VIP")
                
        if expired:
            self._save_database()
        return expired
        
    def get_near_expiry_vip(self) -> List[Tuple[int, int]]:
        """الحصول على VIP قريب الانتهاء"""
        near = []
        now = datetime.now()
        notify_days = [1, 3, 5]
        
        for mid, exp in self._vip_members.items():
            exp_date = exp if isinstance(exp, datetime) else datetime.fromisoformat(exp)
            days_left = (exp_date - now).days
            
            if days_left in notify_days:
                near.append((mid, days_left))
        return near
        
    # ═══════════════════════════════════════════════════════════════════════════
    # دوال القنوات الإجبارية
    # ═══════════════════════════════════════════════════════════════════════════
    
    def add_mandatory_channel(self, channel: str, max_members: int = 0) -> bool:
        """إضافة قناة إجبارية"""
        channels = self._settings.get('mandatory_channels', [])
        if channel not in channels:
            channels.append(channel)
            self._settings['mandatory_channels'] = channels
            
            if max_members > 0:
                self._mandatory_channels_config[channel] = {
                    'max_members': max_members,
                    'current_members': 0,
                    'added_date': datetime.now().isoformat()
                }
            
            self._save_settings()
            return True
        return False
        
    def increment_mandatory_channel_members(self, channel: str) -> bool:
        """زيادة عداد أعضاء القناة الإجبارية - فقط عند التحقق من الاشتراك"""
        if channel in self._mandatory_channels_config:
            config = self._mandatory_channels_config[channel]
            config['current_members'] = config.get('current_members', 0) + 1
            
            if config['current_members'] >= config.get('max_members', 0) > 0:
                self.remove_mandatory_channel(channel)
                return True
                
            self._save_settings()
        return False
        
    def export_all_data(self) -> dict:
        """تصدير جميع البيانات - بدون تكرار"""
        members_export = {}
        for mid, mdata in self._members.items():
            mcopy = mdata.copy()
            for key in ['first_seen', 'joined_date', 'last_active']:
                if key in mcopy and isinstance(mcopy[key], datetime):
                    mcopy[key] = mcopy[key].isoformat()
            members_export[str(mid)] = mcopy
            
        return {
            'export_date': datetime.now().isoformat(),
            'bot_info': {
                'username': GuardianConfig.BOT_USERNAME,
                'admin_id': GuardianConfig.MASTER_ADMIN_ID,
                'admin_username': GuardianConfig.MASTER_ADMIN_USERNAME
            },
            'members': members_export,
            'protected_channels': self._protected_channels,
            'vip_members': {str(k): v.isoformat() if isinstance(v, datetime) else v for k, v in self._vip_members.items()},
            'active_campaigns': self._active_campaigns,
            'pending_campaigns': self._pending_campaigns,
            'campaign_index': self._campaign_index,
            'campaign_stats': self._campaign_stats,
            'gift_codes': self._gift_codes,
            'used_gifts': {str(k): v for k, v in self._used_gifts.items()},
            'activity_history': self._activity_history,
            'settings': self._settings.copy(),
            'version': '19.0.0'
        }
        
    def import_all_data(self, data: dict) -> bool:
        """استيراد جميع البيانات"""
        try:
            self._members.clear()
            self._protected_channels.clear()
            self._vip_members.clear()
            self._active_campaigns.clear()
            self._pending_campaigns.clear()
            self._campaign_index.clear()
            self._campaign_stats.clear()
            self._gift_codes.clear()
            self._used_gifts.clear()
            self._activity_history.clear()
            self._service_categories.clear()
            self._services.clear()
            self._service_orders.clear()
            
            members_data = data.get('members', {})
            for mid_str, mdata in members_data.items():
                mid = int(mid_str)
                mcopy = mdata.copy()
                for key in ['first_seen', 'joined_date', 'last_active']:
                    if key in mcopy and isinstance(mcopy[key], str):
                        try:
                            mcopy[key] = datetime.fromisoformat(mcopy[key])
                        except:
                            mcopy[key] = datetime.now()
                self._members[mid] = mcopy
                
            self._protected_channels = data.get('protected_channels', {})
            
            vip_data = data.get('vip_members', {})
            for mid_str, exp_str in vip_data.items():
                try:
                    self._vip_members[int(mid_str)] = datetime.fromisoformat(exp_str)
                except:
                    pass
                    
            self._active_campaigns = data.get('active_campaigns', {})
            self._pending_campaigns = data.get('pending_campaigns', {})
            self._campaign_index = data.get('campaign_index', {})
            self._campaign_stats = data.get('campaign_stats', {})
            self._gift_codes = data.get('gift_codes', {})
            
            used_data = data.get('used_gifts', {})
            for mid_str, codes in used_data.items():
                self._used_gifts[int(mid_str)] = codes
                
            self._activity_history = data.get('activity_history', [])
            
            imported_settings = data.get('settings', {})
            if imported_settings:
                self._settings.update(imported_settings)
                
            self._admin_list = set(self._settings.get('admin_list', [GuardianConfig.MASTER_ADMIN_ID]))
            self._mandatory_channels_config = self._settings.get('mandatory_channels_config', {})
            
            # تحميل بيانات التحديث من settings فقط
            self._service_categories = self._settings.get('service_categories', {})
            self._services = self._settings.get('services', {})
            self._service_orders = self._settings.get('service_orders', {})
            self._custom_button_names = self._settings.get('custom_button_names', {})
            self._weekly_referral_winners = self._settings.get('weekly_referral_winners', {})
                
            self._save_database()
            self._save_settings()
            self._ensure_master_exists()
            self._init_default_button_names()
            self._rebuild_indexes()
            
            logger.info(f"✅ تم استيراد البيانات: {len(self._members)} عضو")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في استيراد البيانات: {e}")
            return False

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           إنشاء كائن قاعدة البيانات
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

db = MegaDatabase()

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           الدوال المساعدة
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

async def notify_master(context: ContextTypes.DEFAULT_TYPE, text: str):
    """إرسال إشعار للمدير"""
    try:
        await context.bot.send_message(chat_id=GuardianConfig.MASTER_ADMIN_ID, text=f"🔔 إشعار من البوت:\n\n{text}")
    except:
        pass

async def check_mandatory_channels(member_id: int, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, List[dict]]:
    """التحقق من الاشتراك في القنوات الإجبارية - لا يتم زيادة العداد هنا"""
    channels = db._settings.get('mandatory_channels', [])
    not_joined = []
    
    for channel in channels:
        try:
            if 't.me/' in channel:
                username = channel.split('t.me/')[-1].split('/')[0]
                chat_id = f"@{username}"
            elif channel.startswith('@'):
                chat_id = channel
            else:
                chat_id = f"@{channel}"
                
            member = await context.bot.get_chat_member(chat_id, member_id)
            if member.status in ['member', 'administrator', 'creator']:
                pass
            elif member.status in ['left', 'kicked']:
                not_joined.append({
                    'id': chat_id,
                    'link': channel if channel.startswith('http') else f"https://t.me/{chat_id.replace('@', '')}",
                    'name': chat_id
                })
        except:
            pass
            
    return len(not_joined) == 0, not_joined

def generate_qr_code(data: str, member_id: int) -> str:
    """توليد صورة QR Code"""
    os.makedirs(GuardianConfig.QR_FOLDER, exist_ok=True)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1a73e8", back_color="white")
    
    filename = f"{GuardianConfig.QR_FOLDER}/qr_{member_id}.png"
    img.save(filename)
    
    return filename

async def verify_channel_subscription(bot, member_id: int, channel_username: str, channel_id: str = None) -> bool:
    """التحقق من اشتراك العضو في قناة"""
    if channel_username:
        try:
            username = channel_username.replace('https://t.me/', '').replace('@', '').strip()
            username = username.split('/')[0].split('?')[0]
            chat_id = f"@{username}"
            
            member = await bot.get_chat_member(chat_id=chat_id, user_id=member_id)
            
            if member.status in ['member', 'administrator', 'creator']:
                return True
        except:
            pass
    
    if channel_id:
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=member_id)
            
            if member.status in ['member', 'administrator', 'creator']:
                return True
        except:
            pass
    
    return False

def get_btn(key: str) -> str:
    """الحصول على اسم الزر المخصص أو الافتراضي"""
    return db.get_button_name(key)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           لوحات المفاتيح
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def build_main_menu(member_id: int) -> InlineKeyboardMarkup:
    """بناء القائمة الرئيسية"""
    can_use, _ = db.can_use_bot(member_id)
    
    keyboard = []
    
    keyboard.append([
        InlineKeyboardButton(get_btn('menu_protection_system'), callback_data="menu_protection_system"),
        InlineKeyboardButton(get_btn('menu_services'), callback_data="menu_services")
    ])
    
    keyboard.append([
        InlineKeyboardButton(get_btn('menu_exchange'), callback_data="menu_exchange"),
        InlineKeyboardButton(get_btn('menu_funding'), callback_data="menu_funding")
    ])
    
    keyboard.append([
        InlineKeyboardButton(get_btn('menu_referral'), callback_data="menu_referral"),
        InlineKeyboardButton(get_btn('menu_vip'), callback_data="menu_vip")
    ])
    
    keyboard.append([
        InlineKeyboardButton(get_btn('menu_support'), callback_data="menu_support"),
        InlineKeyboardButton(get_btn('menu_account_info'), callback_data="menu_account_info")
    ])
    
    if db.is_admin(member_id):
        keyboard.append([
            InlineKeyboardButton(get_btn('menu_admin'), callback_data="menu_admin")
        ])
    
    return InlineKeyboardMarkup(keyboard)

def build_protection_menu() -> InlineKeyboardMarkup:
    """بناء قائمة نظام الحماية"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 قنواتي", callback_data="menu_my_channels")],
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="menu_add_channel")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="menu_delete_channel")],
        [InlineKeyboardButton("🛡 حظر المنضمين", callback_data="menu_quick_block_join")],
        [InlineKeyboardButton("🚫 حظر المغادرين", callback_data="menu_quick_block_leave")],
        [InlineKeyboardButton("👤 حظر بدون يوزر", callback_data="menu_quick_block_nouser")],
        [InlineKeyboardButton("⚙️ إعدادات الحماية", callback_data="menu_protection")],
        [InlineKeyboardButton("📖 شرح القسم", callback_data="menu_protection_help")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]
    ])

def build_services_menu() -> InlineKeyboardMarkup:
    """بناء قائمة الخدمات"""
    categories = db.get_all_categories()
    keyboard = []
    
    if not categories:
        keyboard.append([InlineKeyboardButton("❌ لا توجد أقسام متاحة", callback_data="no_action")])
    else:
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"service_cat_{cat['id']}")
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)

def build_funding_menu() -> InlineKeyboardMarkup:
    """بناء قائمة التمويل"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ تمويل اعضاء الان", callback_data="fund_create")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]
    ])

def build_admin_panel(member_id: int) -> InlineKeyboardMarkup:
    """بناء لوحة تحكم المدير"""
    is_master = member_id == GuardianConfig.MASTER_ADMIN_ID
    
    keyboard = []
    
    keyboard.append([
        InlineKeyboardButton("📊 احصائيات", callback_data="admin_stats"),
        InlineKeyboardButton("👥 آخر 20 عضو", callback_data="admin_recent")
    ])
    
    keyboard.append([
        InlineKeyboardButton("⭐ أعضاء VIP", callback_data="admin_vip_list"),
        InlineKeyboardButton("🏆 أعلى 10 أرصدة", callback_data="admin_top_balance")
    ])
    
    keyboard.append([
        InlineKeyboardButton("💰 شحن رصيد", callback_data="admin_charge"),
        InlineKeyboardButton("💸 خصم رصيد", callback_data="admin_deduct")
    ])
    keyboard.append([
        InlineKeyboardButton("🎁 انشاء هدية", callback_data="admin_gift"),
        InlineKeyboardButton("📤 شحن الكل", callback_data="admin_charge_all")
    ])
    keyboard.append([
        InlineKeyboardButton("📥 خصم من الكل", callback_data="admin_deduct_all")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🚫 إدارة الحظر", callback_data="admin_blocks"),
        InlineKeyboardButton("📢 قنوات إجبارية", callback_data="admin_mandatory")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔍 بحث عن عضو", callback_data="admin_search"),
        InlineKeyboardButton("📨 رسالة لعضو", callback_data="admin_send_message")
    ])
    
    keyboard.append([
        InlineKeyboardButton("⏳ حملات معلقة", callback_data="admin_pending"),
        InlineKeyboardButton("📋 جميع الحملات", callback_data="admin_campaigns")
    ])
    
    keyboard.append([
        InlineKeyboardButton("📁 إدارة الخدمات", callback_data="admin_services"),
        InlineKeyboardButton("📝 طلبات معلقة", callback_data="admin_pending_orders")
    ])
    
    keyboard.append([
        InlineKeyboardButton("📥 تصدير", callback_data="admin_export"),
        InlineKeyboardButton("📤 استيراد", callback_data="admin_import")
    ])
    
    keyboard.append([
        InlineKeyboardButton("💵 سعر VIP", callback_data="admin_vip_price"),
        InlineKeyboardButton("⏰ التجربة", callback_data="admin_trial_days")
    ])
    keyboard.append([
        InlineKeyboardButton("🎁 المكافآت", callback_data="admin_rewards"),
        InlineKeyboardButton("✏️ أسماء الأزرار", callback_data="admin_button_names")
    ])
    
    if is_master:
        keyboard.append([
            InlineKeyboardButton("👑 رفع مشرف", callback_data="admin_promote"),
            InlineKeyboardButton("⬇️ حذف مشرف", callback_data="admin_demote")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🗑 حذف عضو", callback_data="admin_delete_member"),
        InlineKeyboardButton("🔧 صيانة", callback_data="admin_maintenance")
    ])
    keyboard.append([
        InlineKeyboardButton("📣 اذاعة", callback_data="admin_broadcast"),
        InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def build_service_management_menu() -> InlineKeyboardMarkup:
    """بناء قائمة إدارة الخدمات"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 إضافة قسم", callback_data="admin_add_category")],
        [InlineKeyboardButton("➕ إضافة خدمة", callback_data="admin_add_service")],
        [InlineKeyboardButton("🗑 حذف قسم", callback_data="admin_delete_category_menu")],
        [InlineKeyboardButton("❌ حذف خدمة", callback_data="admin_delete_service_menu")],
        [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]
    ])

def build_button_names_menu() -> InlineKeyboardMarkup:
    """بناء قائمة أسماء الأزرار"""
    buttons = [
        ('menu_services', '⚡ الخدمات'),
        ('menu_protection_system', '🛡 نظام الحماية'),
        ('menu_exchange', '🔄 تبادل اشتراك والربح'),
        ('menu_funding', '💰 تمويل اعضاء'),
        ('menu_referral', '🔗 دعوة صديق'),
        ('menu_vip', '⭐ اشتراك VIP'),
        ('menu_support', '💬 تواصل مع الدعم'),
        ('menu_admin', '🎛 لوحة التحكم'),
        ('menu_account_info', 'ℹ️ معلومات حسابك'),
    ]
    
    keyboard = []
    for key, default in buttons:
        current = db.get_button_name(key)
        keyboard.append([InlineKeyboardButton(f"✏️ {current}", callback_data=f"edit_btn_{key}")])
    
    keyboard.append([InlineKeyboardButton("🔄 استعادة الافتراضية", callback_data="reset_buttons")])
    keyboard.append([InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")])
    return InlineKeyboardMarkup(keyboard)

def build_blocks_menu() -> InlineKeyboardMarkup:
    """بناء قائمة الحظر"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 حظر عضو", callback_data="block_add")],
        [InlineKeyboardButton("✅ فك حظر عضو", callback_data="block_remove")],
        [InlineKeyboardButton("📋 عرض المحظورين", callback_data="block_list")],
        [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]
    ])

def build_rewards_menu() -> InlineKeyboardMarkup:
    """بناء قائمة المكافآت"""
    inviter = db._settings.get('inviter_reward', GuardianConfig.INVITER_REWARD_AMOUNT)
    invited = db._settings.get('invited_reward', GuardianConfig.INVITED_REWARD_AMOUNT)
    subscribe = db._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT)
    funding = db._settings.get('funding_price_per_member', GuardianConfig.FUNDING_PRICE_PER_MEMBER)
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👤 مكافأة الداعي: {inviter} IQD", callback_data="reward_inviter")],
        [InlineKeyboardButton(f"🆕 مكافأة المدعو: {invited} IQD", callback_data="reward_invited")],
        [InlineKeyboardButton(f"✅ مكافأة الاشتراك: {subscribe} IQD", callback_data="reward_subscribe")],
        [InlineKeyboardButton(f"👥 سعر تمويل العضو: {funding} IQD", callback_data="reward_funding")],
        [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]
    ])

def build_mandatory_menu() -> InlineKeyboardMarkup:
    """بناء قائمة القنوات الإجبارية"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="mandatory_add")],
        [InlineKeyboardButton("📋 عرض القنوات", callback_data="mandatory_list")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="mandatory_delete_menu")],
        [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]
    ])

def build_channels_list(member_id: int, prefix: str) -> Optional[InlineKeyboardMarkup]:
    """بناء قائمة القنوات"""
    channels = db.get_member_channels(member_id)
    if not channels:
        return None
        
    keyboard = []
    for ch_id in channels:
        ch_data = db._protected_channels.get(str(ch_id), {})
        title = ch_data.get('title', 'قناة')
        if len(title) > 30:
            title = title[:27] + "..."
        keyboard.append([
            InlineKeyboardButton(f"📢 {title}", callback_data=f"{prefix}_{ch_id}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")])
    return InlineKeyboardMarkup(keyboard)

def build_channel_settings(channel_id: str) -> InlineKeyboardMarkup:
    """بناء إعدادات القناة"""
    settings = db.get_channel_settings(channel_id)
    
    block_join = settings.get('block_new_members', False)
    block_leave = settings.get('block_leaving_members', False)
    block_nouser = settings.get('block_no_username', False)
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"🛡 حظر المنضمين: {'✅ مفعل' if block_join else '❌ معطل'}",
            callback_data=f"toggle_block_new_{channel_id}"
        )],
        [InlineKeyboardButton(
            f"🚫 حظر المغادرين: {'✅ مفعل' if block_leave else '❌ معطل'}",
            callback_data=f"toggle_block_leave_{channel_id}"
        )],
        [InlineKeyboardButton(
            f"👤 حظر بدون يوزر: {'✅ مفعل' if block_nouser else '❌ معطل'}",
            callback_data=f"toggle_block_nouser_{channel_id}"
        )],
        [InlineKeyboardButton("📊 إحصائيات", callback_data=f"stats_{channel_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection")]
    ])

def build_exchange_page(campaigns: List[dict], page: int = 0) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """بناء صفحة تبادل الاشتراك والربح"""
    if not campaigns:
        return "📊 لا توجد قنوات متاحة حالياً للتبادل.\n\nعد في وقت آخر.", None
    
    per_page = GuardianConfig.CHANNELS_PER_PAGE
    total_pages = (len(campaigns) + per_page - 1) // per_page
    
    if page >= total_pages:
        page = 0
    elif page < 0:
        page = total_pages - 1
    
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(campaigns))
    page_campaigns = campaigns[start_idx:end_idx]
    
    total_possible_points = len(campaigns) * db._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT)
    
    text = f"""
📢 اشترك بالقنوات الموجودة للحصول على النقاط

💰 كل قناة تمنحك {db._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT)} نقطة
🎯 إجمالي النقاط الممكنة: {total_possible_points} نقطة
📄 الصفحة {page + 1} من {total_pages}

⚠️ ملاحظة هامة: يجب الاشتراك في القناة أولاً ثم الضغط على زر "تحقق من الاشتراكات" للحصول على النقاط
"""
    
    keyboard = []
    
    for campaign in page_campaigns:
        channel_title = campaign.get('channel_title', 'قناة')
        channel_link = campaign.get('channel_link', '')
        campaign_id = campaign.get('campaign_id', '')
        
        row = []
        if channel_link:
            row.append(InlineKeyboardButton(f"📢 {channel_title[:20]}", url=channel_link))
        else:
            row.append(InlineKeyboardButton(f"📢 {channel_title[:20]}", callback_data="no_link"))
        
        row.append(InlineKeyboardButton("📝 ابلاغ", callback_data=f"report_ex_{campaign_id}_{page}"))
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("✅ تحقق من الاشتراكات", callback_data=f"verify_page_{page}")
    ])
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"exchange_page_{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=f"exchange_page_{page+1}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")])
    
    return text, InlineKeyboardMarkup(keyboard)

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           ديكور الحماية
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def guardian_shield(func):
    """ديكور الحماية"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
        
        if db.is_member_blocked(user.id):
            if update.callback_query:
                await update.callback_query.answer("❌ تم حظر حسابك من استخدام البوت", show_alert=True)
            elif update.message:
                await update.message.reply_text("❌ تم حظر حسابك من استخدام البوت")
            return
        
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            if update.callback_query:
                await update.callback_query.answer("❌ حدث خطأ", show_alert=True)
            raise
    return wrapper

async def check_mandatory_before_action(update: Update, context: ContextTypes.DEFAULT_TYPE, member_id: int) -> bool:
    """التحقق من القنوات الإجبارية"""
    is_joined, not_joined = await check_mandatory_channels(member_id, context)
    
    if not is_joined:
        keyboard = []
        for ch in not_joined:
            btn_text = f"📢 {ch['name'].replace('@', '')[:20]}"
            keyboard.append([InlineKeyboardButton(btn_text, url=ch['link'])])
        keyboard.append([InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="verify_mandatory")])
        
        channels_text = "\n".join([f"• {ch['name']}" for ch in not_joined])
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"⚠️ يجب الاشتراك في جميع القنوات التالية لاستخدام البوت:\n\n"
                f"{channels_text}\n\n"
                f"بعد الاشتراك، اضغط على زر 'تحقق من الاشتراك' للمتابعة.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                f"⚠️ يجب الاشتراك في جميع القنوات التالية لاستخدام البوت:\n\n"
                f"{channels_text}\n\n"
                f"بعد الاشتراك، اضغط على زر 'تحقق من الاشتراك' للمتابعة.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return False
    return True

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           معالج أمر البدء
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

@guardian_shield
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    user = update.effective_user
    member_id = user.id
    message_text = update.message.text or ""
    
    logger.info(f"🚀 العضو {member_id} (@{user.username}) بدأ البوت")
    
    db.update_member_info(member_id, user)
    
    if db.is_member_blocked(member_id):
        await update.message.reply_text(
            "❌ تم حظر حسابك من استخدام البوت.\n\n"
            "إذا كنت تعتقد أن هذا خطأ، يرجى التواصل مع الدعم."
        )
        return
    
    args = context.args
    param = args[0] if args else None
    
    if not param and message_text:
        match = re.search(r'/start[=\s]+(\S+)', message_text)
        if match:
            param = match.group(1)
    
    if param:
        param = param.strip()
        
        try:
            int(param)
            is_gift = False
        except ValueError:
            is_gift = True
        
        if is_gift:
            success, msg = db.redeem_gift_code(param, member_id)
            if success:
                await update.message.reply_text(
                    f"🎁 {msg}\n\n💰 رصيدك الحالي: {db.get_member(member_id).get('balance', 0)} IQD"
                )
                gift = db._gift_codes.get(param)
                if gift and gift.get('used_count', 0) >= gift.get('max_uses', 0):
                    await notify_master(context, f"🎁 انتهى رابط الهدية: {param}")
            else:
                await update.message.reply_text(f"{msg}")
        else:
            inviter_id = int(param)
            if inviter_id != member_id:
                success, msg = db.process_referral(member_id, inviter_id)
                if success:
                    inviter_reward = db._settings.get('inviter_reward', GuardianConfig.INVITER_REWARD_AMOUNT)
                    invited_reward = db._settings.get('invited_reward', GuardianConfig.INVITED_REWARD_AMOUNT)
                    
                    try:
                        await context.bot.send_message(
                            chat_id=inviter_id,
                            text=f"🎉 مبروك! تم تسجيل عضو جديد عبر رابط الإحالة الخاص بك!\n\n"
                                 f"💰 حصلت على مكافأة {inviter_reward} IQD\n"
                                 f"👤 العضو الجديد: @{user.username or user.first_name}"
                        )
                    except:
                        pass
                    
                    await update.message.reply_text(
                        f"🎁 مرحباً بك في بوت تفاعلكم الذكي!\n\n"
                        f"💰 حصلت على مكافأة تسجيل {invited_reward} IQD\n"
                        f"💳 رصيدك الحالي: {db.get_member(member_id).get('balance', 0)} IQD"
                    )
    
    if db._settings.get('maintenance_mode', False) and member_id != GuardianConfig.MASTER_ADMIN_ID:
        await update.message.reply_text(
            "🔧 البوت حالياً تحت الصيانة.\n\n"
            "يرجى المحاولة في وقت لاحق. شكراً لتفهمك."
        )
        return
    
    is_joined, not_joined = await check_mandatory_channels(member_id, context)
    
    if not is_joined:
        keyboard = []
        for ch in not_joined:
            btn_text = f"📢 {ch['name'].replace('@', '')[:20]}"
            keyboard.append([InlineKeyboardButton(btn_text, url=ch['link'])])
        keyboard.append([InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="verify_mandatory")])
        
        channels_text = "\n".join([f"• {ch['name']}" for ch in not_joined])
        
        await update.message.reply_text(
            f"⚠️ يجب الاشتراك في جميع القنوات التالية لاستخدام البوت:\n\n"
            f"{channels_text}\n\n"
            f"بعد الاشتراك، اضغط على زر 'تحقق من الاشتراك'",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    await show_main_menu(update, member_id)

async def show_main_menu(update: Update, member_id: int):
    """عرض القائمة الرئيسية"""
    can_use, status = db.can_use_bot(member_id)
    member = db.get_member(member_id)
    channels_count = len(member.get('protected_channels', []))
    max_channels = db.get_max_channels(member_id)
    price = db._settings.get('vip_price', GuardianConfig.DEFAULT_VIP_PRICE)
    free_days = db._settings.get('free_trial_days', GuardianConfig.FREE_TRIAL_DAYS)
    
    text = f"""
🤖 مرحباً بك في بوت  تفاعلكم 

🛡 حالة حسابك: {status}
💰 رصيدك الحالي: {member.get('balance', 0)} IQD
📊 القنوات المضافة: {channels_count} من {max_channels}

🎁 فترة تجريبية مجانية: {free_days} يوم
⭐ سعر الاشتراك VIP: {price} IQD / شهر

استخدم الأزرار أدناه للتحكم في البوت:
"""
    
    keyboard = build_main_menu(member_id)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text=text, reply_markup=keyboard)

async def show_account_info(update: Update, member_id: int):
    """عرض معلومات الحساب"""
    query = update.callback_query
    member = db.get_member(member_id)
    
    mid = member.get('member_id', 'غير معروف')
    username = member.get('username', 'بدون يوزر')
    display_name = member.get('display_name', '')
    balance = member.get('balance', 0)
    joined = member.get('joined_date', '')
    if isinstance(joined, datetime):
        joined = joined.strftime('%Y-%m-%d %H:%M')
    
    is_vip = "⭐ VIP" if db.is_vip_member(member_id) else "👤 عادي"
    if db.is_vip_member(member_id):
        expiry = db.get_vip_expiry_date(member_id)
        if expiry:
            days_left = (expiry - datetime.now()).days
            is_vip = f"⭐ VIP | متبقي {days_left} يوم"
    
    can_use, status = db.can_use_bot(member_id)
    channels_count = len(member.get('protected_channels', []))
    referrals_count = len(member.get('referred_members', []))
    referral_earnings = member.get('referral_earnings', 0)
    campaigns_completed = len(member.get('completed_campaigns', []))
    campaign_earnings = member.get('campaign_earnings', 0)
    
    inviter_reward = db._settings.get('inviter_reward', GuardianConfig.INVITER_REWARD_AMOUNT)
    invited_reward = db._settings.get('invited_reward', GuardianConfig.INVITED_REWARD_AMOUNT)
    
    text = f"""
ℹ️ معلومات حسابك

🆔 الايدي: `{mid}`
👤 الاسم: {display_name}
📱 اليوزر: @{username}
💰 الرصيد: {balance} IQD
📅 تاريخ التسجيل: {joined}
🛡 حالة الحساب: {status}
⭐ الاشتراك: {is_vip}

📊 إحصائيات:
• القنوات المحمية: {channels_count}
• عدد المدعوين: {referrals_count}
• أرباح الإحالات: {referral_earnings} IQD
• الحملات المكتملة: {campaigns_completed}
• أرباح الحملات: {campaign_earnings} IQD

💰 مكافآت الإحالة:
• مكافأة الداعي: {inviter_reward} IQD
• مكافأة المدعو: {invited_reward} IQD

📞 للدعم: @{GuardianConfig.MASTER_ADMIN_USERNAME}
"""
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]]),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           معالج الأزرار التفاعلية
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

@guardian_shield
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأزرار التفاعلية"""
    query = update.callback_query
    member_id = update.effective_user.id
    data = query.data
    
    if db.is_member_blocked(member_id) and member_id != GuardianConfig.MASTER_ADMIN_ID:
        await query.edit_message_text("❌ تم حظر حسابك.")
        return
    
    if data not in ["menu_main", "verify_mandatory", "menu_account_info"] and member_id != GuardianConfig.MASTER_ADMIN_ID:
        if not await check_mandatory_before_action(update, context, member_id):
            return
    
    # ═══════════════ القائمة الرئيسية والمعلومات ═══════════════
    if data == "menu_main":
        await show_main_menu(update, member_id)
    
    elif data == "menu_account_info":
        await show_account_info(update, member_id)
    
    elif data == "verify_mandatory":
        # عند الضغط على تحقق - هنا فقط يتم زيادة العداد
        is_joined, _ = await check_mandatory_channels(member_id, context)
        if is_joined:
            # زيادة عداد القنوات الإجبارية
            channels = db._settings.get('mandatory_channels', [])
            for ch in channels:
                db.increment_mandatory_channel_members(ch)
            await query.edit_message_text("✅ تم التحقق من اشتراكك! أهلاً بك في البوت.")
            await show_main_menu(update, member_id)
        else:
            await query.answer("❌ لم تشترك في جميع القنوات المطلوبة!", show_alert=True)
    
    # ═══════════════ نظام الحماية ═══════════════
    elif data == "menu_protection_system":
        await query.edit_message_text(
            "🛡 نظام الحماية المتكامل\n\nاختر ما تريد القيام به:",
            reply_markup=build_protection_menu()
        )
    
    elif data == "menu_protection_help":
        await query.edit_message_text(
            "📖 شرح قسم نظام الحماية\n\n"
            "🛡 هذا القسم يمكنك من حماية قناتك من:\n\n"
            "1️⃣ حظر المنضمين الجدد:\n"
            "• عند تفعيله، أي شخص ينضم إلى قناتك يتم حظره تلقائياً\n\n"
            "2️⃣ حظر المغادرين:\n"
            "• عند تفعيله، أي شخص يغادر قناتك يتم حظره تلقائياً\n\n"
            "3️⃣ حظر بدون يوزر:\n"
            "• عند تفعيله، أي شخص بدون يوزر ينضم يتم حظره\n\n"
            "📋 قنواتي: عرض القنوات المضافة\n"
            "➕ إضافة قناة: إضافة قناة جديدة للحماية\n"
            "🗑 حذف قناة: حذف قناة من الحماية\n"
            "⚙️ إعدادات الحماية: تخصيص الحماية لكل قناة على حدة\n\n"
            "⚠️ شروط الحماية:\n"
            "• يجب رفع البوت أدمن في القناة\n"
            "• منح البوت صلاحيات الحظر وحذف الرسائل\n"
            "• البوت لا يستطيع حظر المشرفين أو المالك",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")]])
        )
    
    elif data == "menu_add_channel":
        channels = db.get_member_channels(member_id)
        max_channels = db.get_max_channels(member_id)
        
        if len(channels) >= max_channels:
            await query.edit_message_text(
                f"❌ لقد وصلت للحد الأقصى من القنوات المسموح بها ({max_channels} قنوات).\n\n"
                f"لإضافة المزيد، قم بحذف قناة موجودة أو اشترك في VIP للحصول على {GuardianConfig.VIP_CHANNELS_LIMIT} قنوات.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")]])
            )
            return
        
        await query.edit_message_text(
            "📢 إضافة قناة حماية جديدة\n\n"
            "أرسل رابط القناة التي تريد إضافتها:\n\n"
            "مثال:\n"
            "• https://t.me/username\n"
            "• @username\n\n"
            "⚠️ شروط إضافة القناة:\n"
            "• يجب رفع البوت أدمن في القناة\n"
            "• يجب منح البوت صلاحيات: حذف الرسائل، حظر المستخدمين، إضافة مشرفين",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_protection_system")]])
        )
        context.user_data['PROT_ACTION'] = 'add_channel'
        return 1
    
    elif data == "menu_delete_channel":
        keyboard = build_channels_list(member_id, "del")
        if keyboard:
            await query.edit_message_text(
                "🗑 اختر القناة التي تريد حذفها من الحماية:",
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text(
                "❌ ليس لديك أي قنوات حماية مضافة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")]])
            )
    
    elif data.startswith("del_"):
        channel_id = data.replace("del_", "")
        db.remove_protected_channel(member_id, channel_id)
        await query.edit_message_text(
            "✅ تم حذف القناة من قائمة الحماية بنجاح!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 نظام الحماية", callback_data="menu_protection_system")]])
        )
    
    elif data == "menu_my_channels":
        channels = db.get_member_channels(member_id)
        if not channels:
            await query.edit_message_text(
                "❌ ليس لديك أي قنوات حماية مضافة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")]])
            )
            return
            
        text = "📋 قنوات الحماية الخاصة بك:\n\n"
        for ch_id in channels:
            ch_data = db._protected_channels.get(str(ch_id), {})
            text += f"• {ch_data.get('title', 'قناة بدون اسم')}\n"
            
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")]])
        )
    
    elif data == "menu_protection":
        keyboard = build_channels_list(member_id, "settings")
        if keyboard:
            await query.edit_message_text(
                "⚙️ اختر القناة لتعديل إعدادات الحماية:",
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text(
                "❌ ليس لديك أي قنوات حماية مضافة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")]])
            )
    
    elif data.startswith("settings_"):
        channel_id = data.replace("settings_", "")
        keyboard = build_channel_settings(channel_id)
        ch_data = db._protected_channels.get(str(channel_id), {})
        title = ch_data.get('title', 'القناة')
        
        await query.edit_message_text(
            f"⚙️ إعدادات الحماية لقناة: {title}\n\nاختر الإعداد الذي تريد تعديله:",
            reply_markup=keyboard
        )
    
    elif data.startswith("toggle_"):
        parts = data.split("_")
        if len(parts) >= 4:
            setting = f"{parts[1]}_{parts[2]}"
            channel_id = parts[3]
            
            db.toggle_channel_protection(channel_id, setting)
            keyboard = build_channel_settings(channel_id)
            ch_data = db._protected_channels.get(str(channel_id), {})
            title = ch_data.get('title', 'القناة')
            
            await query.answer("✅ تم التحديث", show_alert=True)
            await query.edit_message_text(
                f"⚙️ إعدادات الحماية لقناة: {title}\n\nاختر الإعداد الذي تريد تعديله:",
                reply_markup=keyboard
            )
    
    elif data.startswith("stats_"):
        channel_id = data.replace("stats_", "")
        ch_data = db._protected_channels.get(str(channel_id), {})
        title = ch_data.get('title', 'القناة')
        stats = ch_data.get('stats', {})
        
        text = f"📊 إحصائيات قناة: {title}\n\n"
        text += f"👥 عدد الأعضاء الذين انضموا: {stats.get('total_joined', 0)}\n"
        text += f"🚪 عدد الأعضاء الذين غادروا: {stats.get('total_left', 0)}\n"
        text += f"🔨 عدد الأعضاء المحظورين: {stats.get('total_blocked', 0)}\n"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"settings_{channel_id}")]])
        )
    
    # الحماية السريعة
    elif data == "menu_quick_block_join":
        await handle_quick_protection(update, context, member_id, "block_new_members", "حظر المنضمين الجدد")
    elif data == "menu_quick_block_leave":
        await handle_quick_protection(update, context, member_id, "block_leaving_members", "حظر المغادرين")
    elif data == "menu_quick_block_nouser":
        await handle_quick_protection(update, context, member_id, "block_no_username", "حظر بدون يوزر")
    
    # ═══════════════ الخدمات ═══════════════
    elif data == "menu_services":
        await query.edit_message_text(
            "⚡ قسم الخدمات\n\nاختر القسم الذي تريد تصفح خدماته:",
            reply_markup=build_services_menu()
        )
    
    elif data.startswith("service_cat_"):
        cat_id = data.replace("service_cat_", "")
        services = db.get_category_services(cat_id)
        cat_data = db._service_categories.get(cat_id, {})
        cat_name = cat_data.get('name', 'القسم')
        cat_desc = cat_data.get('description', '')
        
        if not services:
            await query.edit_message_text(
                f"📁 {cat_name}\n{cat_desc}\n\n❌ لا توجد خدمات في هذا القسم حالياً.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الأقسام", callback_data="menu_services")]])
            )
            return
        
        keyboard = []
        for srv in services:
            keyboard.append([
                InlineKeyboardButton(f"📌 {srv['name']}", callback_data=f"service_view_{srv['id']}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 الأقسام", callback_data="menu_services")])
        
        await query.edit_message_text(
            f"📁 {cat_name}\n{cat_desc}\n\nاختر الخدمة:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("service_view_"):
        srv_id = data.replace("service_view_", "")
        srv = db._services.get(srv_id)
        
        if not srv:
            await query.answer("❌ الخدمة غير موجودة", show_alert=True)
            return
        
        text = f"""
📌 {srv['name']}

📝 الوصف: {srv['description']}
💰 السعر لكل 1000: {srv['price_per_1000']} IQD
⏰ المدة المتوقعة: {srv['duration']}
📊 الحد الأدنى: {srv['min_amount']}
📊 الحد الأقصى: {srv['max_amount']}
🔗 الرابط: إجباري

هل تريد تقديم طلب لهذه الخدمة؟
"""
        keyboard = [
            [InlineKeyboardButton("✅ تقديم طلب", callback_data=f"order_service_{srv_id}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data=f"service_cat_{srv['category_id']}")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("order_service_"):
        srv_id = data.replace("order_service_", "")
        srv = db._services.get(srv_id)
        
        if not srv:
            await query.answer("❌ الخدمة غير موجودة", show_alert=True)
            return
        
        context.user_data['ORDER_SRV_ID'] = srv_id
        context.user_data['ORDER_SRV_PRICE'] = srv['price_per_1000']
        context.user_data['ORDER_SRV_NAME'] = srv['name']
        context.user_data['ORDER_MIN'] = srv['min_amount']
        context.user_data['ORDER_MAX'] = srv['max_amount']
        context.user_data['ORDER_ACTION'] = 'wait_quantity'
        
        await query.edit_message_text(
            f"📌 {srv['name']}\n\n"
            f"أرسل العدد المطلوب:\n"
            f"الحد الأدنى: {srv['min_amount']}\n"
            f"الحد الأقصى: {srv['max_amount']}\n"
            f"السعر لكل 1000: {srv['price_per_1000']} IQD",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_services")]])
        )
        return 37
    
    # ═══════════════ التبادل والتمويل ═══════════════
    elif data == "menu_exchange":
        campaigns = db.get_uncompleted_campaigns_for_member(member_id)
        text, keyboard = build_exchange_page(campaigns, 0)
        
        if keyboard is None:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")]]))
        else:
            await query.edit_message_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    
    elif data.startswith("exchange_page_"):
        page = int(data.replace("exchange_page_", ""))
        campaigns = db.get_uncompleted_campaigns_for_member(member_id)
        text, keyboard = build_exchange_page(campaigns, page)
        
        if keyboard is None:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")]]))
        else:
            await query.edit_message_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    
    elif data.startswith("verify_page_"):
        page = int(data.replace("verify_page_", ""))
        
        all_campaigns = db.get_uncompleted_campaigns_for_member(member_id)
        per_page = GuardianConfig.CHANNELS_PER_PAGE
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, len(all_campaigns))
        page_campaigns = all_campaigns[start_idx:end_idx]
        
        if not page_campaigns:
            await query.answer("❌ لا توجد قنوات في هذه الصفحة", show_alert=True)
            return
        
        await query.answer("⏳ جاري التحقق من اشتراكاتك...", show_alert=False)
        
        subscribed_ids = []
        for campaign in page_campaigns:
            is_sub = await verify_channel_subscription(
                context.bot, member_id,
                campaign.get('channel_username', '') or campaign.get('channel_link', ''),
                campaign.get('channel_id', '')
            )
            if is_sub:
                subscribed_ids.append(campaign['campaign_id'])
                logger.info(f"✅ العضو {member_id} مشترك في {campaign.get('channel_title', '')}")
            else:
                logger.info(f"❌ العضو {member_id} غير مشترك في {campaign.get('channel_title', '')}")
        
        if subscribed_ids:
            count, successful = db.verify_member_subscriptions(member_id, subscribed_ids)
            
            if count > 0:
                reward_per = db._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT)
                total_reward = count * reward_per
                
                await query.answer(f"✅ تمت إضافة {total_reward} نقطة لرصيدك! ({count} قناة)", show_alert=True)
                
                for cid in successful:
                    camp = db.get_campaign(cid)
                    if camp:
                        try:
                            owner_id = camp['owner_id']
                            await context.bot.send_message(
                                chat_id=owner_id,
                                text=f"✅ عضو جديد اشترك في قناتك!\n\n"
                                     f"📺 {camp.get('channel_title', '')}\n"
                                     f"👤 @{update.effective_user.username or update.effective_user.first_name}\n"
                                     f"🎯 متبقي: {camp.get('members_remaining', 0)} عضو"
                            )
                        except:
                            pass
            else:
                await query.answer("❌ لم تتم إضافة نقاط (ربما حصلت عليها مسبقاً)", show_alert=True)
        else:
            await query.answer("❌ لم يتم التحقق من أي اشتراك! تأكد من اشتراكك في القنوات.", show_alert=True)
        
        campaigns = db.get_uncompleted_campaigns_for_member(member_id)
        text, keyboard = build_exchange_page(campaigns, page)
        if keyboard is None:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")]]))
        else:
            await query.edit_message_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    
    elif data.startswith("report_ex_"):
        parts = data.split("_")
        campaign_id = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 0
        
        await query.edit_message_text(
            "📝 الإبلاغ عن قناة تمويل\n\nأرسل سبب الإبلاغ:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data=f"exchange_page_{page}")]])
        )
        context.user_data['REPORT_ID'] = campaign_id
        context.user_data['REPORT_PAGE'] = page
        context.user_data['REPORT_ACTION'] = 'report_campaign'
        return 12
    
    elif data == "menu_funding":
        await query.edit_message_text(
            "💰 قسم التمويل\n\nيمكنك تمويل قناتك بعدد من الأعضاء للمساعدة في زيادة التفاعل.",
            reply_markup=build_funding_menu()
        )
        
    elif data == "fund_create":
        price = db._settings.get('funding_price_per_member', GuardianConfig.FUNDING_PRICE_PER_MEMBER)
        await query.edit_message_text(
            f"⚡ تمويل اعضاء الان\n\n"
            f"💰 سعر العضو الواحد: {price} IQD\n\n"
            f"📢 أرسل رابط قناتك التي تريد تمويلها:\n"
            f"مثال: @username أو https://t.me/username\n\n"
            f"⚠️ ملاحظات مهمة:\n"
            f"• يجب رفع البوت أدمن في القناة مع جميع الصلاحيات\n"
            f"• بعد إرسال الطلب، سيتم مراجعته من قبل الإدارة\n"
            f"• عند الموافقة، سيتم إضافة القناة إلى قسم تبادل الاشتراك والربح\n"
            f"• لا يمكنك إنشاء حملة لنفس القناة إذا كانت هناك حملة نشطة",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_funding")]])
        )
        context.user_data['FUND_ACTION'] = 'funding_channel'
        return 10
    
    # ═══════════════ الإحالة ═══════════════
    elif data == "menu_referral":
        member = db.get_member(member_id)
        invited = len(member.get('referred_members', []))
        earned = member.get('referral_earnings', 0)
        link = db.get_referral_link(member_id)
        
        inviter_reward = db._settings.get('inviter_reward', GuardianConfig.INVITER_REWARD_AMOUNT)
        invited_reward = db._settings.get('invited_reward', GuardianConfig.INVITED_REWARD_AMOUNT)
        
        top_referrers = db.get_top_referrers(5)
        top_text = ""
        if top_referrers:
            top_text = "\n🏆 أفضل 5 مشاركين:\n"
            for i, ref in enumerate(top_referrers, 1):
                ref_id = ref.get('member_id', 'غير معروف')
                ref_count = len(ref.get('referred_members', []))
                if ref_count > 0:
                    medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1] if i <= 5 else f"{i}️⃣"
                    top_text += f"{medal} ايدي: `{ref_id}` ({ref_count} دعوة)\n"
        
        text = f"""
🔗 نظام دعوة الأصدقاء

🎁 شارك رابط الدعوة الخاص بك واربح المكافآت!

📊 إحصائياتك:
• عدد الأشخاص الذين دعوتهم: {invited}
• إجمالي أرباحك من الإحالات: {earned} IQD

💰 المكافآت:
• أنت تحصل على: {inviter_reward} IQD عن كل صديق يسجل
• صديقك يحصل على: {invited_reward} IQD عند التسجيل
{top_text}

🔗 رابط الدعوة الخاص بك:
`{link}`

انسخ الرابط وأرسله لأصدقائك للربح!
"""
        keyboard = [
            [InlineKeyboardButton("📤 مشاركة رابط الدعوة", switch_inline_query=link)],
            [InlineKeyboardButton("📱 استخراج باركود", callback_data=f"qr_code_{member_id}")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("qr_code_"):
        target_id = int(data.replace("qr_code_", ""))
        link = db.get_referral_link(target_id)
        
        try:
            qr_path = generate_qr_code(link, target_id)
            
            caption = f"""
📱 الباركود الخاص بدعوة الأصدقاء

🔗 الرابط: {link}

👤 العضو: {target_id}

📤 شارك هذا الباركود مع أصدقائك للانضمام إلى البوت والحصول على المكافآت!
"""
            with open(qr_path, 'rb') as f:
                await context.bot.send_photo(
                    chat_id=member_id,
                    photo=f,
                    caption=caption
                )
            
            await query.answer("✅ تم إنشاء الباركود بنجاح!", show_alert=True)
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء الباركود: {e}")
            await query.answer("❌ فشل إنشاء الباركود", show_alert=True)
    
    # ═══════════════ VIP والدعم ═══════════════
    elif data == "menu_vip":
        member = db.get_member(member_id)
        price = db._settings.get('vip_price', GuardianConfig.DEFAULT_VIP_PRICE)
        
        if db.is_vip_member(member_id):
            expiry = db.get_vip_expiry_date(member_id)
            if expiry:
                days = (expiry - datetime.now()).days
                await query.edit_message_text(
                    f"✅ أنت مشترك VIP حالياً!\n\n"
                    f"📅 المتبقي على اشتراكك: {days} يوم\n"
                    f"💰 رصيدك الحالي: {member.get('balance', 0)} IQD\n\n"
                    f"مميزات VIP:\n"
                    f"• إضافة حتى {GuardianConfig.VIP_CHANNELS_LIMIT} قنوات حماية\n"
                    f"• أولوية في الدعم الفني",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")]])
                )
                return
                
        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الاشتراك", callback_data="confirm_vip")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="menu_main")]
        ]
        
        await query.edit_message_text(
            f"⭐ الاشتراك في VIP\n\n"
            f"💰 سعر الاشتراك: {price} IQD\n"
            f"📅 مدة الاشتراك: {GuardianConfig.VIP_DURATION_DAYS} يوم\n"
            f"💳 رصيدك الحالي: {member.get('balance', 0)} IQD\n\n"
            f"مميزات VIP:\n"
            f"• إضافة حتى {GuardianConfig.VIP_CHANNELS_LIMIT} قنوات حماية\n"
            f"• أولوية في الدعم الفني\n"
            f"• مميزات حصرية قادمة\n\n"
            f"📞 لشحن الرصيد، تواصل مع الدعم: @{GuardianConfig.MASTER_ADMIN_USERNAME}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif data == "confirm_vip":
        success, message = db.subscribe_vip(member_id)
        if success:
            await query.edit_message_text(
                f"{message}\n\n🎉 يمكنك الآن الاستمتاع بجميع مميزات VIP!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]])
            )
            await notify_master(context, f"⭐ العضو {member_id} اشترك في VIP!")
        else:
            await query.edit_message_text(
                f"{message}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_vip")]])
            )
    
    elif data == "menu_support":
        await query.edit_message_text(
            f"💬 تواصل مع مسؤول البوت\n\n"
            f"👤 للدعم الفني والاستفسارات:\n"
            f"تيليجرام: @{GuardianConfig.MASTER_ADMIN_USERNAME}\n\n"
            f"📞 للشحن والمساعدة:\n"
            f"راسل الدعم مباشرة على الرابط أعلاه",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📱 راسل @{GuardianConfig.MASTER_ADMIN_USERNAME}", url=f"https://t.me/{GuardianConfig.MASTER_ADMIN_USERNAME}")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="menu_main")]
            ])
        )
    
    # ═══════════════ لوحة التحكم ═══════════════
    elif data == "menu_admin":
        if not db.is_admin(member_id):
            await query.answer("❌ غير مصرح لك بالوصول إلى لوحة التحكم", show_alert=True)
            return
        await query.edit_message_text(
            "🎛 لوحة تحكم المدير\n\nاختر العملية المطلوبة:",
            reply_markup=build_admin_panel(member_id)
        )
    
    # إدارة الخدمات
    elif data == "admin_services":
        if not db.is_admin(member_id): return
        await query.edit_message_text(
            "📁 إدارة قسم الخدمات\n\nاختر العملية:",
            reply_markup=build_service_management_menu()
        )
    
    elif data == "admin_add_category":
        if not db.is_admin(member_id): return
        await query.edit_message_text(
            "📁 إضافة قسم جديد\n\nأرسل اسم القسم:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
        )
        context.user_data['ADMIN_ACTION'] = 'add_category_name'
        return 28
    
    elif data == "admin_add_service":
        if not db.is_admin(member_id): return
        categories = db.get_all_categories()
        if not categories:
            await query.edit_message_text(
                "❌ لا توجد أقسام. أضف قسماً أولاً.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")]])
            )
            return
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"add_srv_to_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")])
        await query.edit_message_text("اختر القسم لإضافة الخدمة إليه:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("add_srv_to_"):
        cat_id = data.replace("add_srv_to_", "")
        context.user_data['SRV_CAT_ID'] = cat_id
        await query.edit_message_text(
            "➕ إضافة خدمة جديدة\n\n"
            "الخطوة 1 من 6:\n"
            "أرسل اسم الخدمة:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
        )
        context.user_data['ADMIN_ACTION'] = 'add_service_name'
        return 30
    
    elif data == "admin_delete_category_menu":
        if not db.is_admin(member_id): return
        categories = db.get_all_categories()
        if not categories:
            await query.edit_message_text("❌ لا توجد أقسام.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")]]))
            return
        keyboard = [[InlineKeyboardButton(f"🗑 {cat['name']}", callback_data=f"delcat_{cat['id']}")] for cat in categories]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")])
        await query.edit_message_text("اختر القسم الذي تريد حذفه:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("delcat_"):
        cat_id = data.replace("delcat_", "")
        if db.delete_category(cat_id):
            await query.answer("✅ تم حذف القسم بنجاح مع جميع خدماته")
        else:
            await query.answer("❌ فشل حذف القسم")
        await query.edit_message_text("✅ تم حذف القسم بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")]]))
    
    elif data == "admin_delete_service_menu":
        if not db.is_admin(member_id): return
        if not db._services:
            await query.edit_message_text("❌ لا توجد خدمات.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")]]))
            return
        keyboard = [[InlineKeyboardButton(f"❌ {srv['name']}", callback_data=f"delsrv_{srv_id}")] for srv_id, srv in db._services.items()]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")])
        await query.edit_message_text("اختر الخدمة التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("delsrv_"):
        srv_id = data.replace("delsrv_", "")
        if db.delete_service(srv_id):
            await query.answer("✅ تم حذف الخدمة بنجاح")
        else:
            await query.answer("❌ فشل حذف الخدمة")
        await query.edit_message_text("✅ تم حذف الخدمة بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_services")]]))
    
    # الطلبات المعلقة
    elif data == "admin_pending_orders":
        if not db.is_admin(member_id): return
        pending_orders = db.get_pending_orders()
        if not pending_orders:
            await query.edit_message_text("📝 لا توجد طلبات معلقة حالياً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            return
        
        for order in pending_orders[:1]:
            user = db.get_member(order['user_id'])
            service = db._services.get(order['service_id'], {})
            category = db._service_categories.get(order.get('category_id', ''), {})
            
            text = f"""
📝 طلب خدمة جديد

🆔 رقم الطلب: `{order['order_id']}`
👤 المستخدم: {user.get('display_name', '')} (@{user.get('username', 'بدون')})
🆔 ايدي المستخدم: `{order['user_id']}`
📁 القسم: {category.get('name', 'غير معروف')}
📌 الخدمة: {order.get('service_name', '')}
📊 الكمية: {order['quantity']}
💰 السعر لكل 1000: {service.get('price_per_1000', 0)} IQD
💵 التكلفة الإجمالية: {order['total_cost']} IQD
🔗 الرابط: {order.get('link', 'غير مطلوب')}
📅 تاريخ الطلب: {order.get('created_at', '')}
"""
            keyboard = [
                [
                    InlineKeyboardButton("✅ موافقة", callback_data=f"approve_order_{order['order_id']}"),
                    InlineKeyboardButton("❌ رفض", callback_data=f"reject_order_{order['order_id']}")
                ],
                [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("approve_order_"):
        order_id = data.replace("approve_order_", "")
        order = db.get_order(order_id)
        if db.approve_order(order_id):
            await query.answer("✅ تمت الموافقة", show_alert=True)
            if order:
                try:
                    await context.bot.send_message(chat_id=order['user_id'], text=f"✅ تمت الموافقة على طلبك!\n\n📌 الخدمة: {order.get('service_name', '')}\n🆔 رقم الطلب: `{order_id}`", parse_mode=ParseMode.MARKDOWN)
                except: pass
        await query.edit_message_text("✅ تمت الموافقة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الطلبات", callback_data="admin_pending_orders")]]))
    
    elif data.startswith("reject_order_"):
        order_id = data.replace("reject_order_", "")
        order = db.get_order(order_id)
        if db.reject_order(order_id):
            await query.answer("❌ تم الرفض", show_alert=True)
            if order:
                try:
                    await context.bot.send_message(chat_id=order['user_id'], text=f"❌ تم رفض طلبك.\n\n📌 الخدمة: {order.get('service_name', '')}\n💰 تم إعادة {order['total_cost']} IQD إلى رصيدك\n🆔 رقم الطلب: `{order_id}`", parse_mode=ParseMode.MARKDOWN)
                except: pass
        await query.edit_message_text("❌ تم الرفض وإعادة المبلغ.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الطلبات", callback_data="admin_pending_orders")]]))
    
    # أسماء الأزرار
    elif data == "admin_button_names":
        if not db.is_admin(member_id): return
        await query.edit_message_text("✏️ تغيير أسماء أزرار واجهة المستخدم\n\nاختر الزر:", reply_markup=build_button_names_menu())
    
    elif data.startswith("edit_btn_"):
        btn_key = data.replace("edit_btn_", "")
        context.user_data['EDIT_BTN_KEY'] = btn_key
        current_name = db.get_button_name(btn_key)
        await query.edit_message_text(f"✏️ الاسم الحالي: {current_name}\n\nأرسل الاسم الجديد:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_button_names")]]))
        context.user_data['ADMIN_ACTION'] = 'edit_button_name'
        return 39
    
    elif data == "reset_buttons":
        if not db.is_admin(member_id): return
        for key in list(db._custom_button_names.keys()):
            db._custom_button_names.pop(key, None)
        db._init_default_button_names()
        db._save_settings()
        await query.edit_message_text("✅ تم استعادة الأسماء الافتراضية.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
    
    # باقي لوحة التحكم
    elif data == "admin_stats":
        if not db.is_admin(member_id): return
        stats = db.get_system_stats()
        text = f"""
📊 إحصائيات النظام الكاملة

👥 إحصائيات الأعضاء:
• إجمالي الأعضاء: {stats['total_members']}
• مشتركي VIP النشطين: {stats['active_vip']}
• الأعضاء المحظورين: {stats['blocked_members']}
• المشرفين: {stats['admin_count']}

📢 إحصائيات القنوات:
• قنوات الحماية: {stats['total_protected_channels']}

💰 إحصائيات مالية:
• إجمالي الأرصدة: {stats['total_balance']} IQD

📊 إحصائيات التمويل:
• إجمالي الحملات: {stats['total_campaigns']}
• حملات معلقة: {stats['pending_campaigns']}
• حملات نشطة: {stats['active_campaigns_count']}
• حملات مكتملة: {stats['completed_campaigns']}

📁 الخدمات:
• الأقسام: {stats['total_categories']}
• الخدمات: {stats['total_services']}
• الطلبات المعلقة: {stats['pending_orders']}

🎁 روابط الهدايا النشطة: {stats['active_gifts']}

⚙️ الإعدادات الحالية:
• سعر الاشتراك VIP: {db._settings.get('vip_price', 0)} IQD
• فترة التجربة المجانية: {db._settings.get('free_trial_days', 0)} يوم
"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 تحديث", callback_data="admin_stats")], [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
    
    elif data == "admin_recent":
        if not db.is_admin(member_id): return
        members = db.get_recent_members(20)
        text = "👥 آخر 20 عضو سجلوا في البوت:\n\n"
        for m in members:
            mid = m.get('member_id', 'غير معروف')
            username = m.get('username', 'بدون')
            balance = m.get('balance', 0)
            blocked = "🚫" if m.get('is_blocked') else "✅"
            vip = "⭐" if db.is_vip_member(mid) else "👤"
            text += f"{blocked}{vip} {mid} | @{username} | {balance} IQD\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
    
    elif data == "admin_vip_list":
        if not db.is_admin(member_id): return
        vip_members = db.get_all_vip_members()
        text = "⭐ المشتركون في VIP:\n\n"
        for mid, exp in vip_members:
            days = (exp - datetime.now()).days
            if days >= 0:
                text += f"🆔 {mid} | 📅 متبقي {days} يوم\n"
            else:
                text += f"🆔 {mid} | ⏰ منتهي\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
    
    elif data == "admin_top_balance":
        if not db.is_admin(member_id): return
        top_members = db.get_top_balance_members(10)
        text = "🏆 أعلى 10 أعضاء رصيداً:\n\n"
        for i, m in enumerate(top_members, 1):
            mid = m.get('member_id', '?')
            username = m.get('username', 'بدون')
            display_name = m.get('display_name', '')
            balance = m.get('balance', 0)
            text += f"{i}. 🆔 {mid} | @{username} | {display_name}\n   💰 {balance} IQD\n\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
    
    elif data == "admin_charge":
        if not db.is_admin(member_id): return
        await query.edit_message_text("💰 شحن رصيد لعضو\n\nأرسل ايدي العضو الذي تريد شحن الرصيد له:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'charge_user_id'
        return 2
    
    elif data == "admin_deduct":
        if not db.is_admin(member_id): return
        await query.edit_message_text("💸 خصم رصيد من عضو\n\nأرسل ايدي العضو الذي تريد الخصم منه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'deduct_user_id'
        return 44
    
    elif data == "admin_charge_all":
        if not db.is_admin(member_id): return
        await query.edit_message_text("📤 شحن رصيد لجميع المستخدمين\n\nأرسل المبلغ المراد شحنه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'charge_all_amount'
        return 42
    
    elif data == "admin_deduct_all":
        if not db.is_admin(member_id): return
        await query.edit_message_text("📥 خصم رصيد من جميع المستخدمين\n\nأرسل المبلغ المراد خصمه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'deduct_all_amount'
        return 40
    
    elif data == "admin_gift":
        if not db.is_admin(member_id): return
        await query.edit_message_text("🎁 انشاء رابط هدية\n\nأرسل عدد الأعضاء المسموح لهم باستخدام الرابط:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'gift_uses'
        return 17
    
    elif data == "admin_blocks":
        if not db.is_admin(member_id): return
        await query.edit_message_text("🚫 إدارة حظر الأعضاء\n\nاختر العملية المطلوبة:", reply_markup=build_blocks_menu())
    
    elif data == "block_add":
        if not db.is_admin(member_id): return
        await query.edit_message_text("🚫 حظر عضو\n\nأرسل ايدي العضو الذي تريد حظره:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_blocks")]]))
        context.user_data['ADMIN_ACTION'] = 'block_user'
        return 19
    
    elif data == "block_remove":
        if not db.is_admin(member_id): return
        await query.edit_message_text("✅ فك حظر عضو\n\nأرسل ايدي العضو الذي تريد فك الحظر عنه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_blocks")]]))
        context.user_data['ADMIN_ACTION'] = 'unblock_user'
        return 20
    
    elif data == "block_list":
        if not db.is_admin(member_id): return
        blocked = db.get_blocked_members()
        if not blocked:
            text = "✅ لا يوجد أعضاء محظورين حالياً."
        else:
            text = f"🚫 قائمة الأعضاء المحظورين ({len(blocked)}):\n\n"
            for m in blocked[:20]:
                text += f"🆔 {m['member_id']} | @{m.get('username', 'بدون')}\n"
                text += f"   👤 {m.get('display_name', '')}\n"
                text += f"   📝 سبب الحظر: {m.get('block_reason', 'غير محدد')}\n\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_blocks")]]))
    
    elif data == "admin_mandatory":
        if not db.is_admin(member_id): return
        await query.edit_message_text("📢 إدارة قنوات الاشتراك الإجباري\n\nاختر العملية المطلوبة:", reply_markup=build_mandatory_menu())
    
    elif data == "mandatory_add":
        if not db.is_admin(member_id): return
        await query.edit_message_text("📢 إضافة قناة اشتراك اجباري\n\nأرسل رابط القناة أو معرفها:\nمثال: @username أو https://t.me/username", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_mandatory")]]))
        context.user_data['ADMIN_ACTION'] = 'add_mandatory_channel'
        return 4
    
    elif data == "mandatory_list":
        if not db.is_admin(member_id): return
        channels = db._settings.get('mandatory_channels', [])
        if not channels:
            text = "❌ لا توجد قنوات اشتراك اجباري مضافة."
        else:
            text = "📋 قنوات الاشتراك الإجباري:\n\n"
            for i, ch in enumerate(channels, 1):
                config = db._mandatory_channels_config.get(ch, {})
                max_members = config.get('max_members', 0)
                current = config.get('current_members', 0)
                extra = f" | 👥 {current}/{max_members}" if max_members > 0 else ""
                text += f"{i}. {ch}{extra}\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_mandatory")]]))
    
    elif data == "mandatory_delete_menu":
        if not db.is_admin(member_id): return
        channels = db._settings.get('mandatory_channels', [])
        if not channels:
            await query.edit_message_text("❌ لا توجد قنوات للحذف.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_mandatory")]]))
            return
        keyboard = [[InlineKeyboardButton(f"🗑 {ch[:40]}", callback_data=f"delmand_{ch}")] for ch in channels]
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_mandatory")])
        await query.edit_message_text("اختر القناة التي تريد حذفها من الاشتراك الإجباري:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("delmand_"):
        channel = data.replace("delmand_", "")
        if db.remove_mandatory_channel(channel):
            await query.answer("✅ تم حذف القناة بنجاح")
        else:
            await query.answer("❌ فشل الحذف - القناة غير موجودة")
        await query.edit_message_text("✅ تم حذف القناة من قائمة الاشتراك الإجباري.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_mandatory")]]))
    
    elif data == "admin_pending":
        if not db.is_admin(member_id): return
        pending = db.get_pending_campaigns()
        if not pending:
            await query.edit_message_text("📋 لا توجد حملات تمويل معلقة حالياً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            return
        
        for camp in pending[:1]:
            text = f"⏳ حملة تمويل معلقة\n\n📢 اسم القناة: {camp['channel_title']}\n🔗 رابط القناة: {camp['channel_link']}\n👤 صاحب الحملة: {camp['owner_id']}\n👥 عدد الأعضاء المطلوب: {camp['members_required']}\n💰 التكلفة الإجمالية: {camp['total_cost']} IQD"
            keyboard = [
                [InlineKeyboardButton("✅ موافقة", callback_data=f"approve_{camp['campaign_id']}"), InlineKeyboardButton("❌ رفض", callback_data=f"reject_{camp['campaign_id']}")],
                [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]
            ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
    
    elif data.startswith("approve_"):
        if not db.is_admin(member_id): return
        campaign_id = data.replace("approve_", "")
        success, msg, campaign = db.approve_campaign(campaign_id, member_id)
        if success:
            try:
                await context.bot.send_message(chat_id=campaign['owner_id'], text=f"✅ تمت الموافقة على حملة التمويل الخاصة بك!\n\n📢 القناة: {campaign['channel_title']}\n👥 عدد الأعضاء: {campaign['members_required']}\n\n🎯 تم إضافة قناتك إلى قسم تبادل الاشتراك والربح.")
            except: pass
        await query.answer(msg)
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_pending")]]))
    
    elif data.startswith("reject_"):
        if not db.is_admin(member_id): return
        campaign_id = data.replace("reject_", "")
        await query.edit_message_text("❌ رفض حملة تمويل\n\nأرسل سبب الرفض:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_pending")]]))
        context.user_data['REJECT_CAMP_ID'] = campaign_id
        context.user_data['ADMIN_ACTION'] = 'reject_campaign'
        return 12
    
    elif data == "admin_campaigns":
        if not db.is_admin(member_id): return
        campaigns = list(db._active_campaigns.values())
        active = [c for c in campaigns if c.get('status') == 'active']
        text = f"📋 الحملات النشطة ({len(active)}):\n\n"
        keyboard = []
        for camp in active[-5:]:
            text += f"📢 {camp['channel_title']} | {camp['members_joined']}/{camp['members_required']}\n"
            keyboard.append([InlineKeyboardButton(f"❌ إلغاء", callback_data=f"cancel_{camp['campaign_id']}"), InlineKeyboardButton(f"🚫 حظر", callback_data=f"block_owner_{camp['owner_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_admin")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
    
    elif data.startswith("cancel_"):
        if not db.is_admin(member_id): return
        campaign_id = data.replace("cancel_", "")
        db.cancel_campaign(campaign_id, "إلغاء إداري")
        await query.edit_message_text("✅ تم الإلغاء", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_campaigns")]]))
    
    elif data.startswith("block_owner_"):
        if not db.is_admin(member_id): return
        owner_id = int(data.replace("block_owner_", ""))
        db.block_member(owner_id, "حظر إداري")
        for cid, camp in db._active_campaigns.items():
            if camp['owner_id'] == owner_id and camp.get('status') == 'active':
                db.cancel_campaign(cid, "حظر المالك")
        await query.edit_message_text(f"✅ تم حظر {owner_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_campaigns")]]))
    
    elif data == "admin_search":
        if not db.is_admin(member_id): return
        await query.edit_message_text("🔍 بحث عن عضو\n\nأرسل ايدي العضو للبحث عنه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'search_member'
        return 23
    
    elif data == "admin_send_message":
        if not db.is_admin(member_id): return
        await query.edit_message_text("📨 إرسال رسالة لعضو\n\nأرسل ايدي العضو:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'send_message_user'
        return 24
    
    elif data == "admin_delete_member":
        if not db.is_admin(member_id): return
        await query.edit_message_text("🗑 حذف عضو\n\n⚠️ تحذير: لا يمكن التراجع!\n\nأرسل ايدي العضو:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'delete_member'
        return 22
    
    elif data == "admin_export":
        if not db.is_admin(member_id): return
        export_data = db.export_all_data()
        os.makedirs(GuardianConfig.BACKUP_FOLDER, exist_ok=True)
        filename = f"{GuardianConfig.BACKUP_FOLDER}/export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        with open(filename, 'rb') as f:
            await context.bot.send_document(chat_id=member_id, document=f, caption=f"📥 نسخة احتياطية\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n📦 الإصدار 19.0.0")
        await query.edit_message_text("✅ تم التصدير", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_admin")]]))
    
    elif data == "admin_import":
        if not db.is_admin(member_id): return
        await query.edit_message_text(
            "📤 استيراد بيانات\n\n"
            "أرسل ملف JSON الذي تم تصديره مسبقاً من البوت.\n\n"
            "⚠️ تحذير: سيتم استبدال جميع البيانات الحالية بالبيانات الموجودة في الملف!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]])
        )
        context.user_data['ADMIN_ACTION'] = 'import'
        return 9
    
    elif data == "admin_vip_price":
        if not db.is_admin(member_id): return
        current = db._settings.get('vip_price', GuardianConfig.DEFAULT_VIP_PRICE)
        await query.edit_message_text(f"💵 السعر الحالي: {current}\nأرسل السعر الجديد:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'vip_price'
        return 7
    
    elif data == "admin_trial_days":
        if not db.is_admin(member_id): return
        current = db._settings.get('free_trial_days', GuardianConfig.FREE_TRIAL_DAYS)
        await query.edit_message_text(f"⏰ الفترة الحالية: {current}\nأرسل عدد الأيام:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'trial_days'
        return 8
    
    elif data == "admin_rewards":
        if not db.is_admin(member_id): return
        await query.edit_message_text("🎁 المكافآت:", reply_markup=build_rewards_menu())
    
    elif data == "reward_inviter":
        if not db.is_admin(member_id): return
        current = db._settings.get('inviter_reward', GuardianConfig.INVITER_REWARD_AMOUNT)
        await query.edit_message_text(f"👤 مكافأة الداعي: {current}\nأرسل القيمة:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_rewards")]]))
        context.user_data['ADMIN_ACTION'] = 'inviter_reward'
        return 13
    
    elif data == "reward_invited":
        if not db.is_admin(member_id): return
        current = db._settings.get('invited_reward', GuardianConfig.INVITED_REWARD_AMOUNT)
        await query.edit_message_text(f"🆕 مكافأة المدعو: {current}\nأرسل القيمة:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_rewards")]]))
        context.user_data['ADMIN_ACTION'] = 'invited_reward'
        return 14
    
    elif data == "reward_subscribe":
        if not db.is_admin(member_id): return
        current = db._settings.get('subscribe_reward', GuardianConfig.SUBSCRIBE_REWARD_AMOUNT)
        await query.edit_message_text(f"✅ مكافأة الاشتراك: {current}\nأرسل القيمة:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_rewards")]]))
        context.user_data['ADMIN_ACTION'] = 'subscribe_reward'
        return 15
    
    elif data == "reward_funding":
        if not db.is_admin(member_id): return
        current = db._settings.get('funding_price_per_member', GuardianConfig.FUNDING_PRICE_PER_MEMBER)
        await query.edit_message_text(f"👥 سعر تمويل العضو: {current}\nأرسل السعر:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_rewards")]]))
        context.user_data['ADMIN_ACTION'] = 'funding_price'
        return 16
    
    elif data == "admin_promote":
        if member_id != GuardianConfig.MASTER_ADMIN_ID:
            await query.answer("❌ هذه الميزة للمدير الرئيسي فقط", show_alert=True)
            return
        await query.edit_message_text("👑 رفع مشرف جديد\n\nأرسل ايدي العضو الذي تريد ترقيته كمشرف:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'promote_admin'
        return 26
    
    elif data == "admin_demote":
        if member_id != GuardianConfig.MASTER_ADMIN_ID:
            await query.answer("❌ هذه الميزة للمدير الرئيسي فقط", show_alert=True)
            return
        await query.edit_message_text("⬇️ حذف مشرف\n\nأرسل ايدي المشرف الذي تريد إزالته:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'demote_admin'
        return 27
    
    elif data == "admin_maintenance":
        if not db.is_admin(member_id): return
        current = db._settings.get('maintenance_mode', False)
        db._settings['maintenance_mode'] = not current
        db._save_settings()
        state = "تفعيل" if not current else "تعطيل"
        await query.edit_message_text(f"✅ تم {state} وضع الصيانة", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_admin")]]))
    
    elif data == "admin_broadcast":
        if not db.is_admin(member_id): return
        await query.edit_message_text("📣 اذاعة للجميع\n\nأرسل الرسالة التي تريد إرسالها:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
        context.user_data['ADMIN_ACTION'] = 'broadcast'
        return 6

async def handle_quick_protection(update: Update, context: ContextTypes.DEFAULT_TYPE, member_id: int, setting: str, setting_name: str):
    """معالج الحماية السريعة"""
    query = update.callback_query
    
    channels = db.get_member_channels(member_id)
    if not channels:
        await query.edit_message_text(
            "❌ ليس لديك أي قنوات حماية مضافة.\n\nقم بإضافة قناة أولاً.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة قناة", callback_data="menu_add_channel")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")]
            ])
        )
        return
        
    if len(channels) == 1:
        channel_id = channels[0]
        db.toggle_channel_protection(channel_id, setting)
        ch_data = db._protected_channels.get(str(channel_id), {})
        title = ch_data.get('title', 'القناة')
        
        await query.edit_message_text(
            f"✅ تم {setting_name} في قناة {title}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 نظام الحماية", callback_data="menu_protection_system")]])
        )
    else:
        keyboard = []
        for ch_id in channels:
            ch_data = db._protected_channels.get(str(ch_id), {})
            title = ch_data.get('title', 'قناة')
            if len(title) > 30:
                title = title[:27] + "..."
            keyboard.append([InlineKeyboardButton(f"📢 {title}", callback_data=f"quick_{setting}_{ch_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_protection_system")])
        
        await query.edit_message_text(
            f"اختر القناة التي تريد {setting_name} فيها:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           معالج الرسائل النصية
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

@guardian_shield
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج موحد لجميع الرسائل النصية"""
    member_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""
    
    prot_action = context.user_data.get('PROT_ACTION')
    fund_action = context.user_data.get('FUND_ACTION')
    report_action = context.user_data.get('REPORT_ACTION')
    order_action = context.user_data.get('ORDER_ACTION')
    admin_action = context.user_data.get('ADMIN_ACTION')
    
    logger.info(f"📝 رسالة من {member_id} | admin_action={admin_action}")
    
    # ═══════════════ طلبات الخدمات ═══════════════
    if order_action == 'wait_quantity':
        try:
            quantity = int(text)
            min_qty = context.user_data.get('ORDER_MIN', 1)
            max_qty = context.user_data.get('ORDER_MAX', 999999)
            
            if quantity < min_qty or quantity > max_qty:
                await update.message.reply_text(f"❌ الكمية يجب أن تكون بين {min_qty} و {max_qty}")
                return 37
            
            price_per_1000 = context.user_data.get('ORDER_SRV_PRICE', 0)
            total_cost = int((quantity / 1000) * price_per_1000)
            
            member_balance = db.get_member(member_id).get('balance', 0)
            
            if member_balance < total_cost:
                await update.message.reply_text(
                    f"❌ رصيدك غير كافي.\n💰 رصيدك: {member_balance} IQD\n💵 التكلفة: {total_cost} IQD",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_services")]])
                )
                context.user_data.clear()
                return ConversationHandler.END
            
            context.user_data['ORDER_QTY'] = quantity
            context.user_data['ORDER_COST'] = total_cost
            
            await update.message.reply_text(
                f"📌 الكمية: {quantity}\n💰 التكلفة: {total_cost} IQD\n\n"
                f"🔗 أرسل الرابط المطلوب:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_services")]])
            )
            context.user_data['ORDER_ACTION'] = 'wait_link'
            return 38
                
        except ValueError:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً:")
            return 37
    
    elif order_action == 'wait_link':
        context.user_data['ORDER_LINK'] = text
        await confirm_service_order(update, context, member_id)
        return ConversationHandler.END
    
    # ═══════════════ إضافة قناة حماية ═══════════════
    if prot_action == 'add_channel':
        channel_input = text.strip()
        channel_id = None
        
        if 't.me/' in channel_input:
            parts = channel_input.split('t.me/')
            if len(parts) > 1:
                username = parts[1].split('/')[0].split('?')[0]
                channel_id = f"@{username}"
        elif channel_input.startswith('@'):
            channel_id = channel_input
        else:
            channel_id = f"@{channel_input}"
            
        try:
            chat = await context.bot.get_chat(channel_id)
            bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
            
            if bot_member.status not in ['administrator', 'creator']:
                await update.message.reply_text(
                    "❌ البوت ليس أدمن في هذه القناة.\n\n"
                    "يجب رفع البوت أدمن مع الصلاحيات:\n"
                    "• حذف الرسائل\n• حظر المستخدمين\n• إضافة مشرفين",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 نظام الحماية", callback_data="menu_protection_system")]])
                )
                context.user_data.clear()
                return ConversationHandler.END
                
            member_channels = db.get_member_channels(member_id)
            if str(chat.id) in member_channels:
                await update.message.reply_text(
                    "❌ هذه القناة مضافة مسبقاً.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 نظام الحماية", callback_data="menu_protection_system")]])
                )
                context.user_data.clear()
                return ConversationHandler.END
                
            db.add_protected_channel(member_id, str(chat.id), chat.title)
            
            await update.message.reply_text(
                f"✅ تم إضافة القناة بنجاح!\n\n"
                f"📢 اسم القناة: {chat.title}\n"
                f"🆔 معرف القناة: {chat.id}\n\n"
                f"يمكنك الآن تفعيل ميزات الحماية من 'نظام الحماية'.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛡 نظام الحماية", callback_data="menu_protection_system")],
                    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]
                ])
            )
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except Exception as e:
            await update.message.reply_text("❌ القناة غير موجودة. حاول مرة أخرى:")
            return 1
    
    # ═══════════════ طلب تمويل ═══════════════
    elif fund_action == 'funding_channel':
        channel_input = text.strip()
        channel_id = None
        channel_link = channel_input
        channel_username = ""
        
        if 't.me/' in channel_input:
            parts = channel_input.split('t.me/')
            if len(parts) > 1:
                username = parts[1].split('/')[0].split('?')[0]
                channel_id = f"@{username}"
                channel_username = username
        elif channel_input.startswith('@'):
            channel_id = channel_input
            channel_username = channel_input.replace('@', '')
        else:
            channel_id = f"@{channel_input}"
            channel_username = channel_input
            
        if not channel_link.startswith('http'):
            channel_link = f"https://t.me/{channel_username}"
            
        if db.has_active_campaign_for_channel(member_id, channel_username):
            await update.message.reply_text(
                "❌ لديك حملة تمويل نشطة بالفعل لهذه القناة.\n\n"
                "يرجى الانتظار حتى اكتمال الحملة الحالية.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_funding")]])
            )
            context.user_data.clear()
            return ConversationHandler.END
            
        try:
            chat = await context.bot.get_chat(channel_id)
            bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
            
            if bot_member.status not in ['administrator', 'creator']:
                await update.message.reply_text(
                    "❌ البوت ليس أدمن في القناة.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_funding")]])
                )
                context.user_data.clear()
                return ConversationHandler.END
                
            context.user_data['FUND_CH_ID'] = str(chat.id)
            context.user_data['FUND_CH_TITLE'] = chat.title
            context.user_data['FUND_CH_LINK'] = channel_link
            context.user_data['FUND_CH_USERNAME'] = channel_username
            
            price = db._settings.get('funding_price_per_member', GuardianConfig.FUNDING_PRICE_PER_MEMBER)
            
            await update.message.reply_text(
                f"📢 القناة: {chat.title}\n"
                f"💰 سعر العضو: {price} IQD\n\n"
                f"أرسل عدد الأعضاء المطلوب:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_funding")]])
            )
            
            context.user_data['FUND_ACTION'] = 'funding_members'
            return 11
            
        except Exception as e:
            await update.message.reply_text(f"❌ خطأ. حاول مرة أخرى:")
            return 10
    
    elif fund_action == 'funding_members':
        try:
            members_count = int(text)
            if members_count <= 0:
                await update.message.reply_text("❌ العدد > 0")
                return 11
                
            price = db._settings.get('funding_price_per_member', GuardianConfig.FUNDING_PRICE_PER_MEMBER)
            total_cost = members_count * price
            
            member = db.get_member(member_id)
            
            if member.get('balance', 0) < total_cost:
                await update.message.reply_text(
                    f"❌ رصيدك غير كافي\n💰 رصيدك: {member.get('balance', 0)}\n💵 التكلفة: {total_cost}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_funding")]])
                )
                context.user_data.clear()
                return ConversationHandler.END
                
            member['balance'] -= total_cost
            
            success, result = db.create_pending_campaign(
                member_id, context.user_data['FUND_CH_ID'], context.user_data['FUND_CH_TITLE'],
                context.user_data['FUND_CH_LINK'], context.user_data['FUND_CH_USERNAME'], members_count
            )
            
            if not success:
                member['balance'] += total_cost
                await update.message.reply_text(
                    f"{result}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="menu_funding")]])
                )
                context.user_data.clear()
                return ConversationHandler.END
            
            await update.message.reply_text(
                f"✅ تم إنشاء طلب التمويل بنجاح!\n\n"
                f"📢 القناة: {context.user_data['FUND_CH_TITLE']}\n"
                f"👥 عدد الأعضاء: {members_count}\n"
                f"💰 التكلفة: {total_cost} IQD\n\n"
                f"⏳ طلبك قيد المراجعة من قبل الإدارة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]])
            )
            
            await notify_master(context, f"📢 طلب تمويل جديد!\n👤 {member_id}\n📺 {context.user_data['FUND_CH_TITLE']}\n👥 {members_count}\n💰 {total_cost} IQD")
            
            context.user_data.clear()
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("❌ أرسل رقماً صحيحاً:")
            return 11
    
    # ═══════════════ الإبلاغ ═══════════════
    elif report_action == 'report_campaign':
        campaign_id = context.user_data.get('REPORT_ID')
        page = context.user_data.get('REPORT_PAGE', 0)
        
        db.report_campaign(campaign_id, member_id, text)
        
        await update.message.reply_text(
            "✅ تم إرسال البلاغ",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"exchange_page_{page}")]])
        )
        
        await notify_master(context, f"🚨 بلاغ عن حملة!\n👤 {member_id}\n📝 {text}")
        
        context.user_data.clear()
        return ConversationHandler.END
    
    # ═══════════════ لوحة المدير ═══════════════
    if not db.is_admin(member_id):
        return ConversationHandler.END
    
    # --- إضافة قسم ---
    if admin_action == 'add_category_name':
        context.user_data['CAT_NAME'] = text
        await update.message.reply_text(
            f"📁 اسم القسم: {text}\n\nأرسل وصف القسم:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
        )
        context.user_data['ADMIN_ACTION'] = 'add_category_desc'
        return 29
    
    elif admin_action == 'add_category_desc':
        cat_name = context.user_data.get('CAT_NAME', '')
        cat_id = db.create_service_category(cat_name, text)
        await update.message.reply_text(
            f"✅ تم إضافة القسم: {cat_name}\n📝 الوصف: {text}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إدارة الخدمات", callback_data="admin_services")]])
        )
        await notify_master(context, f"📁 تم إضافة قسم خدمات جديد: {cat_name}")
        context.user_data.clear()
        return ConversationHandler.END
    
    # --- إضافة خدمة (6 خطوات) ---
    elif admin_action == 'add_service_name':
        context.user_data['SRV_NAME'] = text
        await update.message.reply_text(
            f"📌 اسم الخدمة: {text}\n\n"
            f"الخطوة 2 من 6:\n"
            f"أرسل وصف الخدمة:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
        )
        context.user_data['ADMIN_ACTION'] = 'add_service_desc'
        return 31
    
    elif admin_action == 'add_service_desc':
        context.user_data['SRV_DESC'] = text
        await update.message.reply_text(
            f"📝 الوصف: {text}\n\n"
            f"الخطوة 3 من 6:\n"
            f"أرسل السعر مقابل كل 1000:\n"
            f"(أرسل رقماً فقط، مثال: 5000)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
        )
        context.user_data['ADMIN_ACTION'] = 'add_service_price'
        return 33
    
    elif admin_action == 'add_service_price':
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ السعر يجب أن يكون أكبر من 0، أرسل رقماً صحيحاً:")
                return 33
            context.user_data['SRV_PRICE'] = price
            await update.message.reply_text(
                f"💰 السعر لكل 1000: {price} IQD\n\n"
                f"الخطوة 4 من 6:\n"
                f"كم هي المدة المتوقعة لتسليم الخدمة؟\n"
                f"(مثال: 24 ساعة، 3 أيام، أسبوع)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
            )
            context.user_data['ADMIN_ACTION'] = 'add_service_duration'
            return 34
        except ValueError:
            await update.message.reply_text("❌ رقم غير صالح، أرسل رقماً صحيحاً:")
            return 33
    
    elif admin_action == 'add_service_duration':
        context.user_data['SRV_DURATION'] = text
        await update.message.reply_text(
            f"⏰ المدة المتوقعة: {text}\n\n"
            f"الخطوة 5 من 6:\n"
            f"ما هو الحد الأدنى للطلب؟\n"
            f"(أرسل رقماً)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
        )
        context.user_data['ADMIN_ACTION'] = 'add_service_min'
        return 35
    
    elif admin_action == 'add_service_min':
        try:
            min_val = int(text)
            if min_val <= 0:
                await update.message.reply_text("❌ الحد الأدنى يجب أن يكون أكبر من 0:")
                return 35
            context.user_data['SRV_MIN'] = min_val
            await update.message.reply_text(
                f"📊 الحد الأدنى: {min_val}\n\n"
                f"الخطوة 6 من 6:\n"
                f"ما هو الحد الأقصى للطلب؟\n"
                f"(أرسل رقماً)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_services")]])
            )
            context.user_data['ADMIN_ACTION'] = 'add_service_max'
            return 36
        except ValueError:
            await update.message.reply_text("❌ رقم غير صالح، أرسل رقماً:")
            return 35
    
    elif admin_action == 'add_service_max':
        try:
            max_val = int(text)
            if max_val <= 0:
                await update.message.reply_text("❌ الحد الأقصى يجب أن يكون أكبر من 0:")
                return 36
            if max_val < context.user_data.get('SRV_MIN', 0):
                await update.message.reply_text("❌ الحد الأقصى يجب أن يكون أكبر من أو يساوي الحد الأدنى:")
                return 36
            
            # إضافة الخدمة مباشرة
            srv_id = db.add_service_to_category(
                context.user_data.get('SRV_CAT_ID', ''),
                context.user_data.get('SRV_NAME', ''),
                context.user_data.get('SRV_DESC', ''),
                context.user_data.get('SRV_PRICE', 0),
                context.user_data.get('SRV_DURATION', ''),
                context.user_data.get('SRV_MIN', 0),
                max_val
            )
            
            cat_name = db._service_categories.get(context.user_data.get('SRV_CAT_ID', ''), {}).get('name', '')
            
            await update.message.reply_text(
                f"✅ تم إضافة الخدمة بنجاح إلى قسم {cat_name}!\n\n"
                f"📌 اسم الخدمة: {context.user_data.get('SRV_NAME', '')}\n"
                f"📝 الوصف: {context.user_data.get('SRV_DESC', '')}\n"
                f"💰 السعر لكل 1000: {context.user_data.get('SRV_PRICE', 0)} IQD\n"
                f"⏰ المدة المتوقعة: {context.user_data.get('SRV_DURATION', '')}\n"
                f"📊 الحد الأدنى: {context.user_data.get('SRV_MIN', 0)}\n"
                f"📊 الحد الأقصى: {max_val}\n"
                f"🔗 الرابط: إجباري\n\n"
                f"🎯 الخدمة متاحة الآن للمستخدمين",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إدارة الخدمات", callback_data="admin_services")]])
            )
            
            await notify_master(context, f"➕ خدمة جديدة: {context.user_data.get('SRV_NAME', '')}\n💰 {context.user_data.get('SRV_PRICE', 0)} IQD/1000")
            
            context.user_data.clear()
            return ConversationHandler.END
        except ValueError:
            await update.message.reply_text("❌ رقم غير صالح، أرسل رقماً:")
            return 36
    
    # --- استيراد البيانات ---
    elif admin_action == 'import':
        if update.message.document:
            try:
                # التحقق من أن الملف JSON
                if not update.message.document.file_name.endswith('.json'):
                    await update.message.reply_text(
                        "❌ يجب أن يكون الملف بصيغة JSON!\n\n"
                        "الرجاء إرسال ملف بيانات بصيغة .json فقط.\n"
                        "يمكنك الحصول على الملف الصحيح من زر 'تصدير' في لوحة التحكم.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]])
                    )
                    context.user_data.clear()
                    return ConversationHandler.END
                
                # تحميل الملف
                file = await update.message.document.get_file()
                os.makedirs(GuardianConfig.TEMP_FOLDER, exist_ok=True)
                file_path = f"{GuardianConfig.TEMP_FOLDER}/import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                await file.download_to_drive(file_path)
                
                # قراءة الملف
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_data = json.load(f)
                
                # استيراد البيانات
                if db.import_all_data(imported_data):
                    stats = db.get_system_stats()
                    await update.message.reply_text(
                        f"✅ تم استيراد البيانات بنجاح!\n\n"
                        f"📊 إحصائيات البيانات المستوردة:\n"
                        f"👥 عدد الأعضاء: {stats['total_members']}\n"
                        f"📢 قنوات الحماية: {stats['total_protected_channels']}\n"
                        f"📊 إجمالي الحملات: {stats['total_campaigns']}\n"
                        f"⭐ مشتركي VIP النشطين: {stats['active_vip']}\n"
                        f"🚫 الأعضاء المحظورين: {stats['blocked_members']}\n"
                        f"📁 أقسام الخدمات: {stats['total_categories']}\n"
                        f"📌 الخدمات: {stats['total_services']}\n"
                        f"📝 الطلبات المعلقة: {stats['pending_orders']}\n"
                        f"💰 إجمالي الأرصدة: {stats['total_balance']} IQD\n\n"
                        f"🔔 تم استبدال جميع بيانات البوت بالبيانات المستوردة بنجاح!",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]])
                    )
                    await notify_master(context, f"📤 تم استيراد بيانات جديدة!\n👥 {stats['total_members']} عضو\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    await update.message.reply_text(
                        "❌ فشل استيراد البيانات!\n\n"
                        "تأكد من أن الملف سليم وغير تالف.\n"
                        "إذا استمرت المشكلة، تأكد من توافق الملف مع إصدار البوت الحالي.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]])
                    )
                
                # تنظيف الملف المؤقت
                try:
                    os.remove(file_path)
                except:
                    pass
                    
            except json.JSONDecodeError:
                await update.message.reply_text(
                    "❌ الملف غير صالح!\n\n"
                    "الملف ليس بصيغة JSON صحيحة أو أنه تالف.\n"
                    "تأكد من إرسال ملف النسخة الاحتياطية الصحيح.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]])
                )
            except Exception as e:
                logger.error(f"❌ خطأ في الاستيراد: {e}")
                await update.message.reply_text(
                    f"❌ حدث خطأ أثناء استيراد البيانات!\n\n"
                    f"تأكد من أن الملف متوافق مع نظام البوت.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]])
                )
            
            context.user_data.clear()
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ يرجى إرسال ملف JSON!\n\n"
                "الرجاء إرسال ملف البيانات بصيغة .json فقط.\n"
                "يمكنك الحصول على الملف من زر 'تصدير' في لوحة التحكم.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]])
            )
            return 9
    
    # --- باقي إجراءات المدير ---
    elif admin_action == 'edit_button_name':
        db.set_button_name(context.user_data.get('EDIT_BTN_KEY', ''), text)
        await update.message.reply_text(f"✅ تم تغيير اسم الزر إلى: {text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 أسماء الأزرار", callback_data="admin_button_names")]]))
        context.user_data.clear()
        return ConversationHandler.END
    
    elif admin_action == 'charge_user_id':
        try:
            target_id = int(text)
            db.get_member(target_id)
            context.user_data['CHARGE_TARGET'] = target_id
            await update.message.reply_text("💰 أرسل المبلغ (IQD):")
            context.user_data['ADMIN_ACTION'] = 'charge_amount'
            return 3
        except ValueError:
            await update.message.reply_text("❌ ايدي غير صالح:")
            return 2
    
    elif admin_action == 'charge_amount':
        try:
            amount = int(text)
            if amount <= 0: await update.message.reply_text("❌ المبلغ > 0"); return 3
            db.add_balance(context.user_data['CHARGE_TARGET'], amount)
            await update.message.reply_text(f"✅ تم شحن {amount} IQD", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ مبلغ غير صالح:"); return 3
    
    elif admin_action == 'deduct_user_id':
        try:
            target_id = int(text)
            db.get_member(target_id)
            context.user_data['DEDUCT_TARGET'] = target_id
            await update.message.reply_text(f"💸 أرسل المبلغ للخصم من {target_id}:")
            context.user_data['ADMIN_ACTION'] = 'deduct_amount'
            return 45
        except ValueError: await update.message.reply_text("❌ ايدي غير صالح:"); return 44
    
    elif admin_action == 'deduct_amount':
        try:
            amount = int(text)
            if amount <= 0: await update.message.reply_text("❌ المبلغ > 0"); return 45
            nb = db.force_deduct_balance(context.user_data['DEDUCT_TARGET'], amount)
            await update.message.reply_text(f"✅ تم خصم {amount} IQD\n💰 الرصيد: {nb}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ رقم غير صالح"); return 45
    
    elif admin_action == 'charge_all_amount':
        try:
            amount = int(text)
            if amount <= 0: await update.message.reply_text("❌ المبلغ > 0"); return 42
            context.user_data['CHARGE_ALL_AMT'] = amount
            await update.message.reply_text(f"📤 سيتم شحن {amount} IQD للجميع\nأرسل رسالة للمستخدمين:")
            context.user_data['ADMIN_ACTION'] = 'charge_all_message'; return 43
        except ValueError: await update.message.reply_text("❌ رقم"); return 42
    
    elif admin_action == 'charge_all_message':
        amount = context.user_data.get('CHARGE_ALL_AMT', 0)
        await update.message.reply_text("📤 جاري الشحن...")
        count = 0
        for mid in db.get_active_members():
            try: db.add_balance(mid, amount); await context.bot.send_message(chat_id=mid, text=f"{text}\n\n💰 تم شحن {amount} IQD"); count += 1
            except: pass
        await update.message.reply_text(f"✅ تم شحن {amount} IQD لـ {count} عضو", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
        context.user_data.clear(); return ConversationHandler.END
    
    elif admin_action == 'deduct_all_amount':
        try:
            amount = int(text)
            if amount <= 0: await update.message.reply_text("❌ المبلغ > 0"); return 40
            context.user_data['DEDUCT_ALL_AMT'] = amount
            await update.message.reply_text(f"📥 سيتم خصم {amount} IQD من الجميع\nأرسل رسالة للمستخدمين:")
            context.user_data['ADMIN_ACTION'] = 'deduct_all_message'; return 41
        except ValueError: await update.message.reply_text("❌ رقم"); return 40
    
    elif admin_action == 'deduct_all_message':
        amount = context.user_data.get('DEDUCT_ALL_AMT', 0)
        await update.message.reply_text("📥 جاري الخصم...")
        count = 0
        for mid in db.get_active_members():
            try: nb = db.force_deduct_balance(mid, amount); await context.bot.send_message(chat_id=mid, text=f"{text}\n\n💸 تم خصم {amount} IQD\n💰 رصيدك: {nb}"); count += 1
            except: pass
        await update.message.reply_text(f"✅ تم خصم {amount} IQD من {count} عضو", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
        context.user_data.clear(); return ConversationHandler.END
    
    elif admin_action == 'block_user':
        try:
            target_id = int(text)
            if db.get_member(target_id).get('is_blocked'): await update.message.reply_text("❌ محظور بالفعل"); context.user_data.clear(); return ConversationHandler.END
            context.user_data['BLOCK_TARGET'] = target_id
            await update.message.reply_text("📝 أرسل سبب الحظر:")
            context.user_data['ADMIN_ACTION'] = 'block_reason'; return 21
        except ValueError: await update.message.reply_text("❌ ايدي"); return 19
    
    elif admin_action == 'block_reason':
        db.block_member(context.user_data.get('BLOCK_TARGET'), text)
        await update.message.reply_text("✅ تم الحظر", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إدارة الحظر", callback_data="admin_blocks")]]))
        context.user_data.clear(); return ConversationHandler.END
    
    elif admin_action == 'unblock_user':
        try:
            target_id = int(text)
            if not db.get_member(target_id).get('is_blocked'): await update.message.reply_text("❌ ليس محظوراً"); context.user_data.clear(); return ConversationHandler.END
            db.unblock_member(target_id)
            await update.message.reply_text("✅ تم فك الحظر", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إدارة الحظر", callback_data="admin_blocks")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ ايدي"); return 20
    
    elif admin_action == 'add_mandatory_channel':
        context.user_data['MAND_CHANNEL'] = text
        await update.message.reply_text(f"📢 {text}\nأرسل الحد الأقصى (0=بدون):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_mandatory")]]))
        context.user_data['ADMIN_ACTION'] = 'add_mandatory_count'; return 5
    
    elif admin_action == 'add_mandatory_count':
        try:
            mx = max(0, int(text))
            db.add_mandatory_channel(context.user_data.get('MAND_CHANNEL', ''), mx)
            await update.message.reply_text(f"✅ تم", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
        except ValueError: await update.message.reply_text("❌ رقم"); return 5
        context.user_data.clear(); return ConversationHandler.END
    
    elif admin_action == 'reject_campaign':
        success, msg, campaign = db.reject_campaign(context.user_data.get('REJECT_CAMP_ID'), member_id, text)
        if success and campaign:
            try: await context.bot.send_message(chat_id=campaign['owner_id'], text=f"❌ رفضت حملتك\n📝 {text}\n💰 أعيد {campaign['total_cost']} IQD")
            except: pass
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_pending")]]))
        context.user_data.clear(); return ConversationHandler.END
    
    elif admin_action == 'vip_price':
        try:
            p = int(text)
            if p <= 0: await update.message.reply_text("❌ > 0"); return 7
            db._settings['vip_price'] = p; db._save_settings()
            await update.message.reply_text(f"✅ {p}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ رقم"); return 7
    
    elif admin_action == 'trial_days':
        try:
            d = int(text)
            if d <= 0: await update.message.reply_text("❌ > 0"); return 8
            db._settings['free_trial_days'] = d; db._save_settings()
            await update.message.reply_text(f"✅ {d}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ رقم"); return 8
    
    elif admin_action in ['inviter_reward', 'invited_reward', 'subscribe_reward', 'funding_price']:
        try:
            v = int(text)
            if v < 0: await update.message.reply_text("❌ >= 0"); return {'inviter_reward':13,'invited_reward':14,'subscribe_reward':15,'funding_price':16}[admin_action]
            k = {'inviter_reward':'inviter_reward','invited_reward':'invited_reward','subscribe_reward':'subscribe_reward','funding_price':'funding_price_per_member'}[admin_action]
            db._settings[k] = v; db._save_settings()
            await update.message.reply_text(f"✅ {v}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 المكافآت", callback_data="admin_rewards")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ رقم"); return {'inviter_reward':13,'invited_reward':14,'subscribe_reward':15,'funding_price':16}[admin_action]
    
    elif admin_action == 'gift_uses':
        try:
            u = int(text)
            if u <= 0: await update.message.reply_text("❌ > 0"); return 17
            context.user_data['GIFT_USES'] = u
            await update.message.reply_text(f"👥 {u}\n💰 المبلغ لكل عضو:")
            context.user_data['ADMIN_ACTION'] = 'gift_amount'; return 18
        except ValueError: await update.message.reply_text("❌ رقم"); return 17
    
    elif admin_action == 'gift_amount':
        try:
            a = int(text)
            if a <= 0: await update.message.reply_text("❌ > 0"); return 18
            code = db.create_gift_code(member_id, context.user_data.get('GIFT_USES', 0), a)
            link = f"https://t.me/{GuardianConfig.BOT_USERNAME}?start={code}"
            await update.message.reply_text(f"🎁 تم!\n👥 {context.user_data.get('GIFT_USES',0)} | 💰 {a}\n🔗 `{link}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 مشاركة", switch_inline_query=link)], [InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]), parse_mode=ParseMode.MARKDOWN)
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ رقم"); return 18
    
    elif admin_action == 'broadcast':
        await update.message.reply_text("📣 جاري الإرسال...")
        s, f = 0, 0
        for mid in list(db._members.keys()):
            try: await context.bot.send_message(chat_id=int(mid), text=text); s += 1
            except: f += 1
        await update.message.reply_text(f"✅ {s} | ❌ {f}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
        context.user_data.clear(); return ConversationHandler.END
    
    elif admin_action == 'search_member':
        try:
            tid = int(text)
            m = db.search_member(tid)
            if not m: await update.message.reply_text("❌ غير موجود"); context.user_data.clear(); return ConversationHandler.END
            txt = f"🔍 العضو\n🆔 `{tid}`\n👤 {m.get('display_name','')}\n📱 @{m.get('username','-')}\n💰 {m.get('balance',0)} IQD"
            await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 حركات", callback_data=f"show_activity_{tid}")], [InlineKeyboardButton("🔙 رجوع", callback_data="menu_admin")]]), parse_mode=ParseMode.MARKDOWN)
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ ايدي"); return 23
    
    elif admin_action == 'send_message_user':
        try:
            tid = int(text)
            if tid not in db._members: await update.message.reply_text("❌ غير موجود"); context.user_data.clear(); return ConversationHandler.END
            context.user_data['SEND_TARGET'] = tid
            await update.message.reply_text(f"📨 أرسل نص الرسالة للعضو {tid}:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="menu_admin")]]))
            context.user_data['ADMIN_ACTION'] = 'send_message_text'; return 25
        except ValueError: await update.message.reply_text("❌ ايدي"); return 24
    
    elif admin_action == 'send_message_text':
        try: await context.bot.send_message(chat_id=context.user_data.get('SEND_TARGET'), text=f"📨 من الإدارة:\n\n{text}"); await update.message.reply_text("✅ تم")
        except Exception as e: await update.message.reply_text(f"❌ {e}")
        context.user_data.clear(); return ConversationHandler.END
    
    elif admin_action == 'delete_member':
        try:
            tid = int(text)
            if tid == GuardianConfig.MASTER_ADMIN_ID: await update.message.reply_text("❌ لا يمكن حذف المدير!"); context.user_data.clear(); return ConversationHandler.END
            if tid not in db._members: await update.message.reply_text("❌ غير موجود"); context.user_data.clear(); return ConversationHandler.END
            db.delete_member(tid)
            await update.message.reply_text(f"✅ تم حذف {tid}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ ايدي"); return 22
    
    elif admin_action == 'promote_admin':
        try:
            tid = int(text)
            if tid not in db._members: await update.message.reply_text("❌ غير موجود"); context.user_data.clear(); return ConversationHandler.END
            db.promote_admin(tid)
            await update.message.reply_text(f"✅ مشرف جديد: {tid}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ ايدي"); return 26
    
    elif admin_action == 'demote_admin':
        try:
            tid = int(text)
            if tid == GuardianConfig.MASTER_ADMIN_ID: await update.message.reply_text("❌ لا يمكن!"); context.user_data.clear(); return ConversationHandler.END
            db.demote_admin(tid)
            await update.message.reply_text(f"✅ تم إزالة {tid}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة التحكم", callback_data="menu_admin")]]))
            context.user_data.clear(); return ConversationHandler.END
        except ValueError: await update.message.reply_text("❌ ايدي"); return 27

async def confirm_service_order(update: Update, context: ContextTypes.DEFAULT_TYPE, member_id: int):
    """تأكيد طلب الخدمة"""
    srv_id = context.user_data.get('ORDER_SRV_ID', '')
    quantity = context.user_data.get('ORDER_QTY', 0)
    link = context.user_data.get('ORDER_LINK', '')
    total_cost = context.user_data.get('ORDER_COST', 0)
    srv_name = context.user_data.get('ORDER_SRV_NAME', '')
    
    member = db.get_member(member_id)
    member['balance'] = member.get('balance', 0) - total_cost
    
    order_id = db.create_service_order(member_id, srv_id, quantity, link)
    
    text = f"""
✅ تم تقديم طلبك بنجاح!

📌 الخدمة: {srv_name}
📊 الكمية: {quantity}
💰 التكلفة: {total_cost} IQD
🔗 الرابط: {link}
🆔 رقم الطلب: `{order_id}`

⏳ طلبك قيد المراجعة من قبل الإدارة.
سيتم إشعارك عند الموافقة أو الرفض.
"""
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_main")]]),
        parse_mode=ParseMode.MARKDOWN
    )
    
    user = update.effective_user
    await notify_master(context, f"📝 طلب خدمة!\n👤 {user.first_name} (@{user.username})\n📌 {srv_name}\n📊 {quantity}\n💰 {total_cost} IQD\n🔗 {link}")
    
    context.user_data.clear()

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           معالج تحديثات القناة
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

async def handle_channel_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج تحديثات القناة"""
    chat = update.effective_chat
    if not chat:
        return
        
    chat_id = str(chat.id)
    
    if update.my_chat_member:
        new_status = update.my_chat_member.new_chat_member.status
        old_status = update.my_chat_member.old_chat_member.status
        
        if old_status in ['administrator', 'creator'] and new_status in ['member', 'left', 'kicked', 'restricted']:
            logger.info(f"🚨 تم حذف البوت من: {chat.title} ({chat_id})")
            
            channel_username = chat.username or ""
            if channel_username:
                owners = db.cancel_all_campaigns_for_channel(channel_username, "تم حذف البوت من القناة - إلغاء بدون تعويض")
                db.remove_mandatory_channel(channel_username)
                for owner_id in owners:
                    try:
                        await context.bot.send_message(chat_id=owner_id, text=f"🚫 تم إلغاء حملة التمويل لقناتك ({chat.title})\n\n❌ السبب: تم حذف البوت من القناة\n⚠️ لا يوجد تعويض مالي.")
                    except:
                        pass
            
            await notify_master(context, f"🚨 تم حذف البوت من قناة!\n\n📢 {chat.title}\n🆔 {chat_id}\n👤 @{channel_username}\n\nتم إلغاء جميع حملات التمويل المرتبطة.")
            
            if chat_id in db._protected_channels:
                del db._protected_channels[chat_id]
                db._save_database()
    
    if chat_id not in db._protected_channels:
        return
        
    ch_data = db._protected_channels[chat_id]
    settings = ch_data.get('protection_settings', {})
    owner_id = ch_data.get('owner_id')
    
    if not settings or not owner_id:
        return
        
    can_use, _ = db.can_use_bot(owner_id)
    if not can_use:
        return
    
    if update.chat_member and update.chat_member.new_chat_member:
        new_member = update.chat_member.new_chat_member
        user = new_member.user
        user_id = user.id
        
        if user_id == context.bot.id or new_member.status in ['administrator', 'creator']:
            return
            
        ch_data['stats']['total_joined'] = ch_data['stats'].get('total_joined', 0) + 1
        db._save_database()
        
        if settings.get('block_no_username') and not user.username:
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                ch_data['stats']['total_blocked'] = ch_data['stats'].get('total_blocked', 0) + 1
                db._save_database()
            except:
                pass
            return
            
        if settings.get('block_new_members'):
            try:
                await context.bot.ban_chat_member(chat_id, user_id)
                ch_data['stats']['total_blocked'] = ch_data['stats'].get('total_blocked', 0) + 1
                db._save_database()
            except:
                pass
            return
    
    if update.chat_member and update.chat_member.old_chat_member and update.chat_member.new_chat_member:
        old_status = update.chat_member.old_chat_member.status
        new_status = update.chat_member.new_chat_member.status
        
        if old_status == 'member' and new_status == 'left':
            user = update.chat_member.old_chat_member.user
            
            ch_data['stats']['total_left'] = ch_data['stats'].get('total_left', 0) + 1
            db._save_database()
            
            if settings.get('block_leaving_members'):
                try:
                    await context.bot.ban_chat_member(chat_id, user.id)
                    ch_data['stats']['total_blocked'] = ch_data['stats'].get('total_blocked', 0) + 1
                    db._save_database()
                except:
                    pass

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           معالج خاص للأزرار الإضافية
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

async def handle_special_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج خاص للأزرار الإضافية"""
    query = update.callback_query
    data = query.data
    
    if data.startswith("show_activity_"):
        member_id = int(data.replace("show_activity_", ""))
        if not db.is_admin(update.effective_user.id):
            await query.answer("❌ غير مصرح", show_alert=True)
            return
        
        activities = db.get_member_activity(member_id)
        if not activities:
            await query.answer("❌ لا توجد حركات", show_alert=True)
            return
        
        text = f"📋 حركات المستخدم {member_id}:\n\n"
        for log in activities[-50:]:
            timestamp = log.get('timestamp', '')
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime('%Y-%m-%d %H:%M')
            action = log.get('action', '')
            text += f"📅 {timestamp}\n📝 {action}\n{'─' * 30}\n"
        
        file = BytesIO(text.encode('utf-8'))
        file.name = f"activity_{member_id}.txt"
        await context.bot.send_document(chat_id=update.effective_user.id, document=file, caption=f"📋 حركات المستخدم {member_id}")
        await query.answer("✅ تم إرسال الملف", show_alert=True)
    
    elif data.startswith("quick_"):
        parts = data.split("_")
        if len(parts) >= 3:
            setting = f"{parts[1]}_{parts[2]}"
            channel_id = parts[3] if len(parts) > 3 else ""
            if channel_id:
                member_id = update.effective_user.id
                db.toggle_channel_protection(channel_id, setting)
                ch_data = db._protected_channels.get(str(channel_id), {})
                title = ch_data.get('title', 'القناة')
                setting_names = {
                    'block_new_members': 'حظر المنضمين',
                    'block_leaving_members': 'حظر المغادرين',
                    'block_no_username': 'حظر بدون يوزر'
                }
                setting_name = setting_names.get(setting, setting)
                
                await query.edit_message_text(
                    f"✅ تم {setting_name} في قناة {title}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 نظام الحماية", callback_data="menu_protection_system")]])
                )

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           المهام المجدولة
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

async def scheduled_vip_check(context: ContextTypes.DEFAULT_TYPE):
    """فحص انتهاء VIP"""
    expired = db.check_expired_vip()
    for mid in expired:
        try:
            await context.bot.send_message(chat_id=mid, text="⚠️ انتهى اشتراك VIP")
        except:
            pass
    
    near = db.get_near_expiry_vip()
    for mid, days in near:
        try:
            await context.bot.send_message(chat_id=mid, text=f"⏰ VIP ينتهي خلال {days} يوم")
        except:
            pass

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.edit_message_text("❌ تم الإلغاء")
    else:
        await update.message.reply_text("❌ تم الإلغاء")
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#                                           الدالة الرئيسية
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def main():
    """الدالة الرئيسية"""
    
    os.makedirs(GuardianConfig.BACKUP_FOLDER, exist_ok=True)
    os.makedirs(GuardianConfig.TEMP_FOLDER, exist_ok=True)
    os.makedirs(GuardianConfig.LOG_FOLDER, exist_ok=True)
    os.makedirs(GuardianConfig.QR_FOLDER, exist_ok=True)
    
    app = Application.builder().token(GuardianConfig.BOT_TOKEN).concurrent_updates(True).build()
    
    main_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_callbacks, pattern="^menu_add_channel$"),
            CallbackQueryHandler(handle_callbacks, pattern="^fund_create$"),
            CallbackQueryHandler(handle_callbacks, pattern="^report_ex_"),
            CallbackQueryHandler(handle_callbacks, pattern="^order_service_"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_charge$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_deduct$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_charge_all$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_deduct_all$"),
            CallbackQueryHandler(handle_callbacks, pattern="^block_add$"),
            CallbackQueryHandler(handle_callbacks, pattern="^block_remove$"),
            CallbackQueryHandler(handle_callbacks, pattern="^mandatory_add$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_vip_price$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_trial_days$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_broadcast$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_import$"),
            CallbackQueryHandler(handle_callbacks, pattern="^reward_inviter$"),
            CallbackQueryHandler(handle_callbacks, pattern="^reward_invited$"),
            CallbackQueryHandler(handle_callbacks, pattern="^reward_subscribe$"),
            CallbackQueryHandler(handle_callbacks, pattern="^reward_funding$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_gift$"),
            CallbackQueryHandler(handle_callbacks, pattern="^reject_"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_search$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_send_message$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_delete_member$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_promote$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_demote$"),
            CallbackQueryHandler(handle_callbacks, pattern="^admin_add_category$"),
            CallbackQueryHandler(handle_callbacks, pattern="^add_srv_to_"),
            CallbackQueryHandler(handle_callbacks, pattern="^edit_btn_"),
        ],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            5: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            6: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            7: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            8: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            9: [MessageHandler(filters.Document.ALL | filters.TEXT, handle_all_messages)],
            10: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            11: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            12: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            13: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            14: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            15: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            16: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            17: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            18: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            19: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            20: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            21: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            22: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            23: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            24: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            25: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            26: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            27: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            28: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            29: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            30: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            31: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            33: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            34: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            35: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            36: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            37: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            38: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            39: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            40: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            41: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            42: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            43: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            44: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
            45: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_conversation, pattern="^menu_main$"),
            CallbackQueryHandler(cancel_conversation, pattern="^menu_protection_system$"),
            CallbackQueryHandler(cancel_conversation, pattern="^menu_funding$"),
            CallbackQueryHandler(cancel_conversation, pattern="^menu_services$"),
            CallbackQueryHandler(cancel_conversation, pattern="^admin_services$"),
            CallbackQueryHandler(cancel_conversation, pattern="^admin_blocks$"),
            CallbackQueryHandler(cancel_conversation, pattern="^admin_mandatory$"),
            CallbackQueryHandler(cancel_conversation, pattern="^admin_pending$"),
            CallbackQueryHandler(cancel_conversation, pattern="^admin_rewards$"),
            CallbackQueryHandler(cancel_conversation, pattern="^admin_button_names$"),
            CallbackQueryHandler(cancel_conversation, pattern="^menu_admin$"),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True,
        per_message=False
    )
    app.add_handler(main_conv)
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(CallbackQueryHandler(handle_special_buttons, pattern="^show_activity_|^quick_"))
    app.add_handler(ChatMemberHandler(handle_channel_updates, ChatMemberHandler.CHAT_MEMBER | ChatMemberHandler.MY_CHAT_MEMBER))
    
    if app.job_queue:
        app.job_queue.run_repeating(scheduled_vip_check, interval=3600, first=10)
    
    print("\n" + "=" * 80)
    print("🤖 بوت الحارس الذكي - الإصدار 19.0.0")
    print("=" * 80)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"👤 المدير: @{GuardianConfig.MASTER_ADMIN_USERNAME}")
    print("=" * 80)
    print("✅ جميع الميزات القديمة والجديدة تعمل")
    print("✅ إصلاح استيراد البيانات بالكامل")
    print("✅ إصلاح الحذف النهائي للأقسام والخدمات والقنوات الإجبارية")
    print("✅ نظام اشتراك إجباري - العداد يزيد عند التحقق فقط")
    print("✅ متوافق مع استيراد البيانات")
    print("=" * 80)
    print("🚀 البوت يعمل...")
    print("=" * 80 + "\n")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            logger.info("⚠️ تم إيقاف البوت يدوياً")
            break
        except Exception as e:
            logger.critical(f"💥 خطأ: {e}\n{traceback.format_exc()}")
            logger.info("🔄 إعادة تشغيل البوت بعد 5 ثواني...")
            time.sleep(5)