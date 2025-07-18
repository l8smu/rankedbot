
#!/usr/bin/env python3
"""
Season Reset System - إعادة تعيين شاملة للموسم الجديد
"""

import sqlite3
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('heatseeker_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('SeasonReset')

def reset_new_season():
    """إعادة تعيين شاملة للموسم الجديد"""
    
    print("🎮 إعادة تعيين الموسم الجديد - HEATSEEKER")
    print("=" * 60)
    print()
    
    try:
        # الاتصال بقاعدة البيانات
        conn = sqlite3.connect('players.db')
        c = conn.cursor()
        
        # الحصول على إحصائيات قبل الإعادة
        c.execute("SELECT COUNT(*) FROM players")
        total_players = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM matches")
        total_matches = c.fetchone()[0]
        
        c.execute("SELECT username, mmr, wins, losses FROM players ORDER BY mmr DESC LIMIT 5")
        top_players_before = c.fetchall()
        
        print("📊 إحصائيات الموسم السابق:")
        print("-" * 40)
        print(f"  • إجمالي اللاعبين: {total_players}")
        print(f"  • إجمالي المباريات: {total_matches}")
        print()
        
        print("🏆 أفضل 5 لاعبين قبل الإعادة:")
        print("-" * 40)
        for i, (username, mmr, wins, losses) in enumerate(top_players_before, 1):
            winrate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            print(f"  {i}. {username}: {mmr} MMR ({wins}W/{losses}L - {winrate:.1f}%)")
        print()
        
        # 1. إعادة تعيين جميع إحصائيات اللاعبين
        print("🔄 إعادة تعيين إحصائيات اللاعبين...")
        print("-" * 40)
        
        # إعادة تعيين MMR والانتصارات والهزائم
        c.execute("UPDATE players SET mmr = 1250, wins = 0, losses = 0")
        
        # 2. حذف جميع المباريات السابقة
        print("🗑️ حذف سجل المباريات...")
        print("-" * 40)
        
        c.execute("DELETE FROM matches")
        
        # إعادة تعيين عداد المباريات
        c.execute("DELETE FROM sqlite_sequence WHERE name = 'matches'")
        
        # 3. تنظيف الدردشات الخاصة
        print("🧹 تنظيف الدردشات الخاصة...")
        print("-" * 40)
        
        c.execute("UPDATE private_chats SET is_active = 0")
        
        # 4. تنظيف مباريات الخاصة
        print("🔧 تنظيف المباريات الخاصة...")
        print("-" * 40)
        
        c.execute("UPDATE private_matches SET is_active = 0")
        
        # حفظ التغييرات
        conn.commit()
        
        # التحقق من النتائج
        print("✅ تم الانتهاء من الإعادة!")
        print("=" * 60)
        
        # عرض الإحصائيات الجديدة
        c.execute("SELECT username, mmr, wins, losses FROM players ORDER BY username LIMIT 10")
        players_after = c.fetchall()
        
        print("📈 الإحصائيات بعد الإعادة:")
        print("-" * 40)
        print(f"  • MMR جميع اللاعبين: 1000")
        print(f"  • الانتصارات: 0")
        print(f"  • الهزائم: 0")
        print(f"  • المباريات المحذوفة: {total_matches}")
        print()
        
        print("👥 عينة من اللاعبين بعد الإعادة:")
        print("-" * 40)
        for username, mmr, wins, losses in players_after[:5]:
            print(f"  • {username}: {mmr} MMR ({wins}W/{losses}L)")
        print()
        
        # إنشاء تقرير الموسم
        season_report = {
            'reset_date': datetime.now().isoformat(),
            'previous_season': {
                'total_players': total_players,
                'total_matches': total_matches,
                'top_players': top_players_before
            },
            'new_season': {
                'starting_mmr': 1250,
                'reset_complete': True
            }
        }
        
        # تسجيل الإجراء في السجلات
        logger.info(f"SEASON RESET: Complete season reset performed")
        logger.info(f"SEASON RESET: {total_players} players reset to 1000 MMR")
        logger.info(f"SEASON RESET: {total_matches} matches deleted")
        logger.info(f"SEASON RESET: All private chats deactivated")
        
        conn.close()
        
        print("🎉 تم الانتهاء من إعادة تعيين الموسم بنجاح!")
        print("=" * 60)
        print("✅ النتائج:")
        print(f"   • جميع اللاعبين ({total_players}) أصبحوا عند 1000 MMR")
        print(f"   • جميع الإحصائيات صفر (0 انتصار، 0 هزيمة)")
        print(f"   • حُذفت جميع المباريات ({total_matches} مباراة)")
        print(f"   • تم تنظيف الدردشات الخاصة")
        print()
        print("🚀 الموسم الجديد جاهز للبدء!")
        print("   • جميع اللاعبين متساوون في النقاط")
        print("   • منافسة عادلة من البداية")
        print("   • سجل نظيف للمباريات")
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في إعادة التعيين: {e}")
        logger.error(f"Season reset failed: {e}")
        return False

def backup_current_season():
    """إنشاء نسخة احتياطية من الموسم الحالي"""
    
    print("💾 إنشاء نسخة احتياطية...")
    print("-" * 40)
    
    try:
        conn = sqlite3.connect('players.db')
        
        # إنشاء اسم الملف بالتاريخ
        backup_name = f"season_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        # إنشاء النسخة الاحتياطية
        backup_conn = sqlite3.connect(backup_name)
        conn.backup(backup_conn)
        backup_conn.close()
        conn.close()
        
        print(f"✅ تم إنشاء النسخة الاحتياطية: {backup_name}")
        return backup_name
        
    except Exception as e:
        print(f"❌ فشل في إنشاء النسخة الاحتياطية: {e}")
        return None

def show_reset_confirmation():
    """عرض تأكيد إعادة التعيين"""
    
    print("⚠️  تحذير - إعادة تعيين الموسم")
    print("=" * 60)
    print()
    print("هذا الإجراء سيقوم بـ:")
    print("• إعادة تعيين MMR جميع اللاعبين إلى 1000")
    print("• حذف جميع الانتصارات والهزائم")
    print("• حذف سجل جميع المباريات")
    print("• تنظيف الدردشات الخاصة")
    print("• بدء موسم جديد نظيف")
    print()
    print("⚠️  لا يمكن التراجع عن هذا الإجراء!")
    print()
    
    response = input("هل أنت متأكد من إعادة تعيين الموسم؟ (نعم/لا): ").strip().lower()
    
    if response in ['نعم', 'yes', 'y', 'نعم']:
        return True
    else:
        print("❌ تم إلغاء إعادة التعيين")
        return False

if __name__ == "__main__":
    print("🎮 نظام إعادة تعيين الموسم - HEATSEEKER")
    print("=" * 60)
    print()
    
    # عرض التأكيد
    if show_reset_confirmation():
        print()
        
        # إنشاء نسخة احتياطية
        backup_file = backup_current_season()
        
        if backup_file:
            print()
            
            # تنفيذ إعادة التعيين
            if reset_new_season():
                print()
                print("🎊 مبروك! تم إعداد الموسم الجديد بنجاح!")
                print(f"💾 النسخة الاحتياطية محفوظة في: {backup_file}")
            else:
                print("❌ فشل في إعادة تعيين الموسم")
        else:
            print("❌ فشل في إنشاء النسخة الاحتياطية - تم إلغاء العملية")
    else:
        print("✅ تم الاحتفاظ بالموسم الحالي")
