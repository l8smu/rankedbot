# 🎮 دليل تعديل إعدادات الطابور - Queue Configuration Guide

## 📍 مواقع الكود المهمة للتعديل اليدوي

### 1. الإعدادات الأساسية (Basic Settings)
**الملف:** `main.py`
**الخطوط:** 41-44

```python
# Dynamic queue configuration
QUEUE_SIZE = 2  # Default queue size (عدد اللاعبين الكلي)
TEAM_SIZE = 1   # Default team size (عدد اللاعبين في كل فريق)
leaderboard_task = None  # For auto-updating leaderboard
leaderboard_channel = None  # Store leaderboard channel
```

### 2. أمر تغيير عدد اللاعبين (Player Count Command)
**الملف:** `main.py`
**الخطوط:** 2696-2765

```python
@bot.tree.command(name='queueplayer', description='Set the number of players for the queue (2=1v1, 4=2v2, 6=3v3, etc.)')
async def set_queue_players(interaction: discord.Interaction, players: int):
    # التحقق من الأدمن
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can change queue settings!", ephemeral=True)
        return
    
    # تحديث الإعدادات
    global QUEUE_SIZE, TEAM_SIZE
    QUEUE_SIZE = players
    TEAM_SIZE = players // 2
```

### 3. نظام الليدر بورد التلقائي (Auto-Leaderboard System)
**الملف:** `main.py`
**الخطوط:** 2903-2987

```python
@tasks.loop(minutes=30)  # Updates every 30 minutes
async def update_leaderboard():
    """تحديث الليدر بورد تلقائياً"""
    global leaderboard_channel
    
    if not leaderboard_channel:
        return
```

### 4. أمر تحديد قناة الليدر بورد (Set Leaderboard Channel)
**الملف:** `main.py`
**الخطوط:** 2989-3043

```python
@bot.tree.command(name='set_leaderboard', description='Set the current channel as auto-updating leaderboard')
async def set_leaderboard_channel(interaction: discord.Interaction):
    """تحديد قناة الليدر بورد"""
    
    # التحقق من الأدمن
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can set leaderboard channel!", ephemeral=True)
        return
    
    global leaderboard_channel
    leaderboard_channel = interaction.channel
```

## 🔧 كيفية التعديل اليدوي

### تغيير العدد الافتراضي للاعبين:
1. اذهب إلى السطر 42 في `main.py`
2. غير `QUEUE_SIZE = 2` إلى العدد المطلوب
3. غير `TEAM_SIZE = 1` إلى نصف العدد المطلوب

### تغيير مدة تحديث الليدر بورد:
1. اذهب إلى السطر 2904 في `main.py`
2. غير `@tasks.loop(minutes=30)` إلى المدة المطلوبة
3. أمثلة:
   - `@tasks.loop(minutes=15)` - كل 15 دقيقة
   - `@tasks.loop(minutes=60)` - كل ساعة
   - `@tasks.loop(hours=2)` - كل ساعتين

### تغيير حد اللاعبين في الليدر بورد:
1. اذهب إلى السطر 2914 في `main.py`
2. غير `LIMIT 20` إلى العدد المطلوب
3. اذهب إلى السطر 2942 في `main.py`
4. غير `[:10]` إلى العدد المطلوب للعرض

## 📝 أمثلة للتعديل

### للعب 1v1 (لاعبين):
```python
QUEUE_SIZE = 2
TEAM_SIZE = 1
```

### للعب 2v2 (4 لاعبين):
```python
QUEUE_SIZE = 4
TEAM_SIZE = 2
```

### للعب 3v3 (6 لاعبين):
```python
QUEUE_SIZE = 6
TEAM_SIZE = 3
```

### للعب 5v5 (10 لاعبين):
```python
QUEUE_SIZE = 10
TEAM_SIZE = 5
```

## 🎯 الأوامر الجديدة

### أمر تغيير عدد اللاعبين:
```
/queueplayer players:2   # للعب 1v1
/queueplayer players:4   # للعب 2v2
/queueplayer players:6   # للعب 3v3
/queueplayer players:10  # للعب 5v5
```

### أمر تحديد قناة الليدر بورد:
```
/set_leaderboard
```
استخدم هذا الأمر في القناة التي تريد عرض الليدر بورد فيها

## 🔄 إعادة تشغيل البوت

بعد أي تعديل يدوي، يجب إعادة تشغيل البوت:

1. أوقف البوت الحالي
2. احفظ التعديلات
3. شغل البوت مرة أخرى

## 📊 ميزات الليدر بورد التلقائي

- تحديث كل 30 دقيقة تلقائياً
- يعرض أفضل 10 لاعبين
- يحسب نسبة الفوز
- يظهر معلومات الخادم MENA
- يعرض إعداد الطابور الحالي
- يحذف الرسائل القديمة تلقائياً

## 🌍 معلومات إضافية

- جميع المباريات تظهر خادم MENA
- نظام أسماء HSM (HSM1, HSM2, HSM3...)
- أمر إنشاء المباريات المخصصة
- حل مشكلة تكرار الرومات
- نظام طابور مرن يدعم أي عدد من اللاعبين

## 🚀 الميزات الجديدة

✅ تم تغيير الطابور الافتراضي من 4 إلى 2 لاعبين (1v1)
✅ أمر /queueplayer للتحكم في عدد اللاعبين
✅ نظام ليدر بورد تلقائي مع تحديث كل 30 دقيقة
✅ أمر /set_leaderboard لتحديد قناة الليدر بورد
✅ نظام مرن يدعم جميع أحجام الفرق (1v1, 2v2, 3v3, 5v5, إلخ)

## 📁 المسارات المهمة للتعديل

1. **الإعدادات الأساسية**: السطر 42 في `main.py`
2. **أمر تغيير اللاعبين**: السطر 2696 في `main.py`
3. **نظام الليدر بورد**: السطر 2903 في `main.py`
4. **أمر تحديد القناة**: السطر 2989 في `main.py`
5. **تحديث عرض الطابور**: السطر 356 في `main.py`
6. **فحص اكتمال الطابور**: السطر 362 في `main.py`

الآن يمكنك تعديل البوت بسهولة وفقاً لاحتياجاتك!