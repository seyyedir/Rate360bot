import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import time
import os
from flask import Flask, request

# --- تنظیمات ربات ---
API_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not API_TOKEN:
    # اگر در محیط لوکال تست می‌کنید و متغیر محیطی تنظیم نشده، اینجا توکن خود را قرار دهید
    # اما در Render باید آن را به عنوان Environment Variable تنظیم کنید.
    print("Warning: TELEGRAM_BOT_TOKEN environment variable is not set. Using fallback (only for local testing).")
    API_TOKEN = '7742373849:AAEnAGo62b1ts9pP-LGnqqvReI1kQcHxalO' # **توکن ربات شما را اینجا قرار دهید**

BOT_USERNAME = "@Rate360bot"

bot = telebot.TeleBot(API_TOKEN)

# --- ساختار داده‌ها برای ذخیره‌سازی اطلاعات (همانند قبل) ---
assessments = {}
user_states = {}
ALLOWED_PARTICIPANT_COUNTS = [10, 12, 13, 15]

# --- توابع کمکی (همانند قبل) ---
def generate_unique_code():
    while True:
        code = random.randint(1000, 9999)
        if str(code) not in assessments:
            return str(code)

def get_username(message_from_user):
    if message_from_user.username:
        return f"@{message_from_user.username}"
    else:
        return f"{message_from_user.first_name or ''} {message_from_user.last_name or ''}".strip() or "کاربر ناشناس"

def get_participant_list_text(participants_dict):
    if not participants_dict:
        return "هنوز هیچ کاربری تأیید نشده است."
    return "\n".join([f"- {username}" for username in participants_dict.values()])

def is_all_rated(assessment_data):
    num_participants = len(assessment_data['participants'])
    expected_ratings_per_user = num_participants
    for rater_chat_id in assessment_data['participants'].keys():
        if rater_chat_id not in assessment_data['scores'] or \
           len(assessment_data['scores'][rater_chat_id]) < expected_ratings_per_user:
            return False
    return True

# --- هندلرهای دستورات و Callback Queryها (همانند قبل) ---
@bot.message_handler(commands=['start', 'help', 'Run', 'Join', 'Aboutus'])
def handle_commands(message):
    if message.text == '/start':
        bot.reply_to(message, "به ربات امتیازدهی 360 درجه خوش آمدید!\n"
                               "برای ایجاد یک ارزیابی جدید از دستور /Run استفاده کنید.\n"
                               "برای شرکت در یک ارزیابی از دستور /Join استفاده کنید.\n"
                               "برای توضیحات درباره ارزیابی 360 درجه از /Help استفاده کنید.\n"
                               "برای اطلاعات درباره ما از /Aboutus استفاده کنید.")
    elif message.text == '/Help':
        bot.reply_to(message, "مدل ارزیابی 360 درجه یک روش بازخورد جامع است که در آن افراد از همکاران، "
                               "مدیران، زیردستان و حتی خودشان بازخورد دریافت می‌کنند. این مدل به توسعه شخصی و حرفه‌ای کمک می‌کند "
                               "و دیدگاه‌های مختلفی را درباره عملکرد یک فرد ارائه می‌دهد. در این ربات، شما می‌توانید "
                               "یک ارزیابی ایجاد کنید و از شرکت‌کنندگان بخواهید به یکدیگر و خودشان امتیاز دهند.")
    elif message.text == '/Aboutus':
        bot.reply_to(message, "این ربات توسط یک دستیار هوش مصنوعی برای ارزیابی 360 درجه طراحی و پیاده‌سازی شده است.\n"
                               "هدف ما ارائه ابزاری ساده و کارآمد برای جمع‌آوری بازخورد جامع است.")
    elif message.text == '/Run':
        if message.chat.id in user_states:
            bot.reply_to(message, "شما در حال حاضر در یک فرآیند ایجاد/شرکت در ارزیابی هستید. "
                                   "لطفاً ابتدا فرآیند قبلی را تکمیل کنید یا منتظر بمانید.")
            return

        markup = InlineKeyboardMarkup()
        for count in ALLOWED_PARTICIPANT_COUNTS:
            markup.add(InlineKeyboardButton(str(count), callback_data=f"set_max_participants_{count}"))

        user_states[message.chat.id] = {'state': 'waiting_for_max_participants_selection'}
        bot.reply_to(message, "تعداد شرکت‌کنندگان ارزیابی چند نفر باشد؟", reply_markup=markup)

    elif message.text == '/Join':
        if message.chat.id in user_states:
            bot.reply_to(message, "شما در حال حاضر در یک فرآیند ایجاد/شرکت در ارزیابی هستید. "
                                   "لطفاً ابتدا فرآیند قبلی را تکمیل کنید یا منتظر بمانید.")
            return

        user_states[message.chat.id] = {'state': 'waiting_for_assessment_code'}
        bot.reply_to(message, "لطفاً کد ارزیابی را وارد کنید:")

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id]['state'] == 'waiting_for_assessment_code')
def process_assessment_code(message):
    user_id = message.chat.id
    assessment_code = message.text.strip()

    if assessment_code in assessments and assessments[assessment_code]['status'] in ['pending_join', 'pending_start']:
        assessment_data = assessments[assessment_code]
        creator_chat_id = assessment_data['creator_id']

        if user_id in assessment_data['participants']:
            bot.reply_to(message, "شما قبلاً در این ارزیابی ثبت‌نام کرده‌اید و تأیید شده‌اید.")
            del user_states[user_id]
            return

        if user_id in assessment_data['pending_approvals']:
            bot.reply_to(message, "شما قبلاً درخواست شرکت در این ارزیابی را ارسال کرده‌اید و منتظر تأیید مدیر ارزیابی هستید.")
            del user_states[user_id]
            return

        if len(assessment_data['participants']) >= assessment_data['max_participants']:
            bot.reply_to(message, "ظرفیت این ارزیابی تکمیل شده است. لطفا از کدهای دیگر استفاده کنید.")
            del user_states[user_id]
            return

        assessment_data['pending_approvals'][user_id] = get_username(message.from_user)

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ بله تأیید می‌کنم!", callback_data=f"approve_join_{assessment_code}_{user_id}"),
                   InlineKeyboardButton("❌ خیر!", callback_data=f"reject_join_{assessment_code}_{user_id}"))

        bot.send_message(creator_chat_id,
                         f"کاربر **{get_username(message.from_user)}** می‌خواهد در ارزیابی **{assessment_code}** شرکت کند. تأیید می‌کنید؟",
                         parse_mode='Markdown', reply_markup=markup)

        bot.reply_to(message, "بسیار خوب! منتظر تأیید مدیر ارزیابی هستیم.")
        del user_states[user_id]
    else:
        bot.reply_to(message, "کدی که وارد کردید نامعتبر است یا ارزیابی هنوز شروع نشده است. لطفا مجددا تلاش کنید.")
        del user_states[user_id]

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    data = call.data
    user_id = call.message.chat.id

    if data.startswith("set_max_participants_"):
        if user_id in user_states and user_states[user_id]['state'] == 'waiting_for_max_participants_selection':
            max_participants = int(data.split('_')[-1])
            assessment_code = generate_unique_code()

            assessments[assessment_code] = {
                'creator_id': user_id,
                'creator_username': get_username(call.from_user),
                'max_participants': max_participants,
                'participants': {user_id: get_username(call.from_user)},
                'pending_approvals': {},
                'status': 'pending_join',
                'scores': {},
                'start_time': int(time.time()),
                'ratings_count': 0
            }

            bot.edit_message_text(chat_id=user_id,
                                  message_id=call.message.message_id,
                                  text=f"تعداد شرکت‌کنندگان **{max_participants}** نفر تعیین شد.\n"
                                       f"کد ثبت‌نام ارزیابی شما: **{assessment_code}**\n\n"
                                       "این کد را به شرکت‌کنندگان بدهید تا با /Join وارد شوند.")

            participants_info = get_participant_list_text(assessments[assessment_code]['participants'])
            remaining_count = max_participants - len(assessments[assessment_code]['participants'])

            bot.send_message(user_id,
                             f"تأیید شد!\n\n"
                             f"مدیر ارزیابی: {assessments[assessment_code]['creator_username']}\n"
                             f"آیدی ربات: {BOT_USERNAME}\n\n"
                             f"**لیست آیدی تلگرام افراد تأیید شده:**\n{participants_info}\n\n"
                             f"تعداد ثبت‌نام کنندگان: {len(assessments[assessment_code]['participants'])}\n"
                             f"تعداد افراد باقی‌مانده: {remaining_count}", parse_mode='Markdown')

            del user_states[user_id]
            bot.answer_callback_query(call.id, "تعداد شرکت‌کنندگان تعیین شد.")
        else:
            bot.answer_callback_query(call.id, "این عملیات در حال حاضر امکان‌پذیر نیست.")

    elif data.startswith("approve_join_") or data.startswith("reject_join_"):
        parts = data.split('_')
        action = parts[0]
        assessment_code = parts[2]
        target_user_id = int(parts[3])

        if assessment_code not in assessments or user_id != assessments[assessment_code]['creator_id']:
            bot.answer_callback_query(call.id, "شما مجاز به انجام این عملیات نیستید.")
            return

        assessment_data = assessments[assessment_code]

        if target_user_id not in assessment_data['pending_approvals']:
            bot.answer_callback_query(call.id, "این کاربر قبلاً بررسی شده یا درخواست او منقضی شده است.")
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  text=f"درخواست کاربر **{get_username(bot.get_chat_member(target_user_id, target_user_id).user)}** (با شناسه {target_user_id}) قبلاً بررسی شده است.")
            return

        target_username = assessment_data['pending_approvals'].pop(target_user_id)

        if action == 'approve':
            if len(assessment_data['participants']) < assessment_data['max_participants']:
                assessment_data['participants'][target_user_id] = target_username
                bot.answer_callback_query(call.id, "کاربر تأیید شد.")

                participants_info = get_participant_list_text(assessment_data['participants'])
                remaining_count = assessment_data['max_participants'] - len(assessment_data['participants'])

                bot.edit_message_text(chat_id=user_id,
                                      message_id=call.message.message_id,
                                      text=f"**تأیید شد!**\n\n"
                                           f"مدیر ارزیابی: {assessment_data['creator_username']}\n"
                                           f"آیدی ربات: {BOT_USERNAME}\n\n"
                                           f"**لیست آیدی تلگرام افراد تأیید شده:**\n{participants_info}\n\n"
                                           f"تعداد ثبت‌نام کنندگان: {len(assessment_data['participants'])}\n"
                                           f"تعداد افراد باقی‌مانده: {remaining_count}",
                                      parse_mode='Markdown')

                bot.send_message(target_user_id,
                                 f"تبریک میگم! ورود شما به ارزیابی **{assessment_code}** تأیید شد!\n\n"
                                 f"مدیر ارزیابی: {assessment_data['creator_username']}\n"
                                 f"آیدی ربات: {BOT_USERNAME}\n\n"
                                 f"**لیست آیدی تلگرام افرادی که تا الان ثبت‌نام‌شان تأیید شده:**\n{participants_info}\n\n"
                                 f"تعداد ثبت‌نام کنندگان: {len(assessment_data['participants'])}\n"
                                 f"تعداد افراد باقی‌مانده: {remaining_count}",
                                 parse_mode='Markdown')

                if len(assessment_data['participants']) == assessment_data['max_participants']:
                    assessment_data['status'] = 'pending_start'
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("✅ بله شروع شود!", callback_data=f"start_assessment_{assessment_code}"),
                               InlineKeyboardButton("❌ خیر منصرف شدم!", callback_data=f"cancel_assessment_{assessment_code}"))

                    bot.send_message(user_id,
                                     f"**ظرفیت ثبت‌نام ارزیابی {assessment_code} تکمیل شد.**\n\n"
                                     f"**لیست آیدی تلگرام افراد تأیید شده:**\n{participants_info}\n\n"
                                     f"فرایند امتیازدهی شروع شود؟",
                                     parse_mode='Markdown', reply_markup=markup)
            else:
                bot.answer_callback_query(call.id, "ظرفیت ارزیابی تکمیل شده است. نمی‌توانید کاربر بیشتری تأیید کنید.")
                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text=f"درخواست کاربر **{target_username}** برای ارزیابی **{assessment_code}**.\n"
                                           f"**وضعیت:** ظرفیت تکمیل شده است. تأیید نشد.")

        elif action == 'reject':
            bot.answer_callback_query(call.id, "کاربر رد شد.")
            bot.edit_message_text(chat_id=user_id,
                                  message_id=call.message.message_id,
                                  text=f"درخواست کاربر **{target_username}** برای ارزیابی **{assessment_code}** **رد شد.**",
                                  parse_mode='Markdown')
            bot.send_message(target_user_id,
                             f"متأسفانه درخواست شما برای شرکت در ارزیابی **{assessment_code}** توسط مدیر رد شد.")

    elif data.startswith("start_assessment_") or data.startswith("cancel_assessment_"):
        action = data.split('_')[0]
        assessment_code = data.split('_')[2]

        if assessment_code not in assessments or user_id != assessments[assessment_code]['creator_id']:
            bot.answer_callback_query(call.id, "شما مجاز به انجام این عملیات نیستید.")
            return

        assessment_data = assessments[assessment_code]

        if action == 'start':
            assessment_data['status'] = 'in_progress'
            bot.edit_message_text(chat_id=user_id,
                                  message_id=call.message.message_id,
                                  text=f"**فرایند امتیازدهی برای ارزیابی {assessment_code} شروع شد!**",
                                  parse_mode='Markdown')
            bot.answer_callback_query(call.id, "ارزیابی شروع شد.")

            for participant_id, participant_username in assessment_data['participants'].items():
                markup = InlineKeyboardMarkup()
                for target_id, target_username in assessment_data['participants'].items():
                    markup.add(InlineKeyboardButton(f"به {target_username} امتیاز بده", callback_data=f"rate_user_{assessment_code}_{target_id}"))

                bot.send_message(participant_id,
                                 f"**ارزیابی {assessment_code} آغاز شد!**\n"
                                 f"لطفاً به هر یک از افراد لیست (شامل خودتان) از 0 تا 100 امتیاز دهید.",
                                 reply_markup=markup, parse_mode='Markdown')

                user_states[participant_id] = {
                    'state': 'waiting_for_rate_selection',
                    'context': {'assessment_code': assessment_code, 'current_target_id': None}
                }

        elif action == 'cancel':
            assessment_data['status'] = 'cancelled'
            bot.edit_message_text(chat_id=user_id,
                                  message_id=call.message.message_id,
                                  text=f"**پایان نظرسنجی {assessment_code}! (لغو شد)**",
                                  parse_mode='Markdown')
            bot.answer_callback_query(call.id, "ارزیابی لغو شد.")
            for participant_id in assessment_data['participants']:
                if participant_id != user_id:
                    bot.send_message(participant_id, f"مدیر ارزیابی **{assessment_code}** را لغو کرد. نظرسنجی پایان یافت.")
            del assessments[assessment_code]

    @bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id]['state'] == 'waiting_for_score')
    def process_score_input(message):
        user_id = message.chat.id
        state_context = user_states[user_id]['context']
        assessment_code = state_context['assessment_code']
        target_user_id = state_context['target_user_id']
        target_username = state_context['target_username']

        try:
            score = int(message.text)
            if not (0 <= score <= 100):
                raise ValueError("Score out of range")

            if assessment_code not in assessments or assessments[assessment_code]['status'] != 'in_progress':
                bot.reply_to(message, "ارزیابی یافت نشد یا در حال انجام نیست. لطفاً مجدداً تلاش کنید.")
                del user_states[user_id]
                return

            assessment_data = assessments[assessment_code]

            if user_id not in assessment_data['participants']:
                bot.reply_to(message, "شما مجاز به امتیازدهی در این ارزیابی نیستید.")
                del user_states[user_id]
                return

            if user_id not in assessment_data['scores']:
                assessment_data['scores'][user_id] = {}
            assessment_data['scores'][user_id][target_user_id] = score

            del user_states[user_id]

            bot.reply_to(message, f"امتیاز **{score}** برای **{target_username}** ثبت شد.")

            check_and_finalize_assessment(assessment_code)

            markup = InlineKeyboardMarkup()
            for p_id, p_username in assessment_data['participants'].items():
                if user_id not in assessment_data['scores'] or p_id not in assessment_data['scores'][user_id]:
                    markup.add(InlineKeyboardButton(f"به {p_username} امتیاز بده", callback_data=f"rate_user_{assessment_code}_{p_id}"))

            if markup.keyboard:
                bot.send_message(user_id, "به چه کسی امتیاز می‌دهید؟", reply_markup=markup)
            else:
                bot.send_message(user_id, "شما به همه شرکت‌کنندگان امتیاز داده‌اید. ممنونم! برای مشاهده نتایج تا پایان امتیازدهی همه کاربران صبور باشید.")

        except ValueError:
            bot.reply_to(message, "امتیاز نامعتبر است. لطفاً یک عدد صحیح بین 0 تا 100 وارد کنید.")

    def check_and_finalize_assessment(assessment_code):
        assessment_data = assessments[assessment_code]
        num_participants = len(assessment_data['participants'])

        expected_ratings_per_user = num_participants

        all_completed = True
        for p_id in assessment_data['participants'].keys():
            if p_id not in assessment_data['scores'] or len(assessment_data['scores'][p_id]) < expected_ratings_per_user:
                all_completed = False
                break

        if all_completed:
            assessment_data['status'] = 'completed'
            results_text = "نتایج نهایی ارزیابی:\n\n"
            detailed_results_text = "جزئیات امتیازدهی (فقط برای مدیر):\n\n"

            for target_id, target_username in assessment_data['participants'].items():
                total_score = 0
                count = 0
                individual_scores_for_target = []

                for rater_id, rater_scores in assessment_data['scores'].items():
                    if target_id in rater_scores:
                        total_score += rater_scores[target_id]
                        count += 1
                        individual_scores_for_target.append(f"{assessment_data['participants'][rater_id]} (از {rater_id}): {rater_scores[target_id]}")

                avg_score = total_score / count if count > 0 else 0

                results_text += f"**{target_username}:**\n"
                results_text += f"  میانگین امتیاز: **{avg_score:.2f}**\n"
                results_text += f"  جمع امتیازات: **{total_score}**\n\n"

                detailed_result