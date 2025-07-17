
"""
إضافة أمر إعادة تعيين الموسم للبوت
"""

# إضافة هذا الكود إلى main.py

@bot.tree.command(
    name='reset_season',
    description='إعادة تعيين شاملة للموسم الجديد (Admin only)')
@app_commands.default_permissions(administrator=True)
async def reset_season(interaction: discord.Interaction):
    """إعادة تعيين شاملة للموسم الجديد - Admin only"""
    
    await interaction.response.defer()
    
    try:
        # الحصول على الإحصائيات قبل الإعادة
        c.execute("SELECT COUNT(*) FROM players")
        total_players = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM matches")
        total_matches = c.fetchone()[0]
        
        c.execute("SELECT username, mmr, wins, losses FROM players ORDER BY mmr DESC LIMIT 3")
        top_players = c.fetchall()
        
        # إنشاء embed تأكيد
        embed = discord.Embed(
            title="⚠️ تأكيد إعادة تعيين الموسم",
            description="**هذا الإجراء سيحذف جميع الإحصائيات ويبدأ موسم جديد!**",
            color=discord.Color.red())
        
        embed.add_field(
            name="📊 الإحصائيات الحالية",
            value=f"**اللاعبين:** {total_players}\n**المباريات:** {total_matches}",
            inline=True)
        
        if top_players:
            top_3_text = ""
            for i, (username, mmr, wins, losses) in enumerate(top_players, 1):
                top_3_text += f"{i}. {username} ({mmr} MMR)\n"
            
            embed.add_field(
                name="🏆 أفضل 3 لاعبين",
                value=top_3_text,
                inline=True)
        
        embed.add_field(
            name="🔄 ما سيحدث",
            value="• جميع اللاعبين → 1000 MMR\n• جميع الانتصارات/الهزائم → 0\n• حذف سجل المباريات\n• تنظيف الدردشات الخاصة",
            inline=False)
        
        embed.add_field(
            name="⚠️ تحذير مهم",
            value="**لا يمكن التراجع عن هذا الإجراء!**\nسيتم فقدان جميع الإحصائيات نهائياً",
            inline=False)
        
        # إنشاء أزرار التأكيد
        class SeasonResetView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
            
            @discord.ui.button(label="✅ تأكيد إعادة التعيين", 
                             style=discord.ButtonStyle.danger)
            async def confirm_reset(self, button_interaction: discord.Interaction, 
                                  button: discord.ui.Button):
                if button_interaction.user != interaction.user:
                    await button_interaction.response.send_message(
                        "❌ فقط من طلب الأمر يمكنه التأكيد!", ephemeral=True)
                    return
                
                await button_interaction.response.defer()
                
                # تنفيذ إعادة التعيين
                try:
                    # إعادة تعيين اللاعبين
                    c.execute("UPDATE players SET mmr = 1000, wins = 0, losses = 0")
                    
                    # حذف المباريات
                    c.execute("DELETE FROM matches")
                    c.execute("DELETE FROM sqlite_sequence WHERE name = 'matches'")
                    
                    # تنظيف الدردشات
                    c.execute("UPDATE private_chats SET is_active = 0")
                    c.execute("UPDATE private_matches SET is_active = 0")
                    
                    conn.commit()
                    
                    # تنظيف المباريات النشطة في الذاكرة
                    global active_matches, player_queue, match_id_counter
                    active_matches.clear()
                    player_queue.clear()
                    match_id_counter = 1
                    
                    # إنشاء embed النجاح
                    success_embed = discord.Embed(
                        title="🎉 تم إعادة تعيين الموسم بنجاح!",
                        description="**الموسم الجديد جاهز للبدء!**",
                        color=discord.Color.green())
                    
                    success_embed.add_field(
                        name="✅ تم الانتهاء من",
                        value=f"• إعادة تعيين {total_players} لاعب إلى 1000 MMR\n• حذف {total_matches} مباراة\n• تنظيف جميع الدردشات الخاصة\n• مسح الطابور النشط",
                        inline=False)
                    
                    success_embed.add_field(
                        name="🚀 الموسم الجديد",
                        value="• جميع اللاعبين متساوون (1000 MMR)\n• سجل نظيف للمباريات\n• منافسة عادلة من البداية",
                        inline=False)
                    
                    success_embed.set_footer(
                        text=f"تم التنفيذ بواسطة {interaction.user.display_name}")
                    
                    await button_interaction.edit_original_response(
                        embed=success_embed, view=None)
                    
                    # تسجيل في السجلات
                    logger.info(f"SEASON RESET: Complete season reset by {interaction.user.display_name}")
                    logger.info(f"SEASON RESET: {total_players} players reset, {total_matches} matches deleted")
                    
                    # تحديث عرض الطابور إذا كان موجود
                    queue_channel = discord.utils.get(interaction.guild.channels, 
                                                    name=QUEUE_CHANNEL_NAME)
                    if queue_channel:
                        await update_queue_display(queue_channel)
                    
                except Exception as e:
                    error_embed = discord.Embed(
                        title="❌ خطأ في إعادة التعيين",
                        description=f"حدث خطأ أثناء إعادة تعيين الموسم: {e}",
                        color=discord.Color.red())
                    
                    await button_interaction.edit_original_response(
                        embed=error_embed, view=None)
            
            @discord.ui.button(label="❌ إلغاء", style=discord.ButtonStyle.secondary)
            async def cancel_reset(self, button_interaction: discord.Interaction, 
                                 button: discord.ui.Button):
                if button_interaction.user != interaction.user:
                    await button_interaction.response.send_message(
                        "❌ فقط من طلب الأمر يمكنه الإلغاء!", ephemeral=True)
                    return
                
                cancel_embed = discord.Embed(
                    title="✅ تم إلغاء إعادة التعيين",
                    description="تم الاحتفاظ بجميع الإحصائيات والمباريات",
                    color=discord.Color.blue())
                
                await button_interaction.response.edit_message(
                    embed=cancel_embed, view=None)
        
        view = SeasonResetView()
        await interaction.followup.send(embed=embed, view=view)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ خطأ",
            description=f"حدث خطأ أثناء تحضير إعادة التعيين: {e}",
            color=discord.Color.red())
        
        await interaction.followup.send(embed=error_embed)
