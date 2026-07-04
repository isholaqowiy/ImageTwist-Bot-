import os
import logging
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

import image_processor
import utils

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# State machine states
MENU_CHOICE, AWAITING_SINGLE_UPLOAD, ROTATE_OPT, FLIP_OPT, RESIZE_OPT, AWAITING_BATCH = range(6)

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("🖼 Upload Image", callback_data="menu_upload")],
        [InlineKeyboardButton("🔄 Rotate Image", callback_data="menu_rotate"),
         InlineKeyboardButton("↔️ Flip Image", callback_data="menu_flip")],
        [InlineKeyboardButton("📏 Resize Image", callback_data="menu_resize"),
         InlineKeyboardButton("📦 Batch Processing", callback_data="menu_batch")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    utils.ensure_temp_directory()
    welcome = (
        "👋 Welcome to *ImageTwist Bot*!\n"
        "Edit your images in seconds with simple and powerful tools.\n\n"
        "🖼 *Upload an image*\n"
        "🔄 *Rotate to any angle*\n"
        "↔ *Flip horizontally or vertically*\n"
        "📏 *Resize while maintaining quality*\n"
        "⚡ *Fast, secure, and easy to use*\n\n"
        "Tap a button below or send an image to get started."
    )
    if update.message:
        await update.message.reply_text(welcome, reply_markup=get_main_menu(), parse_mode="Markdown")
    return MENU_CHOICE

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "❓ *ImageTwist Help Manual*\n\n"
        "1. Tap *Upload Image* and send any image file (up to 20MB).\n"
        "2. Select your transformation option (Rotate, Flip, or Resize).\n"
        "3. The bot processes your image instantly with zero quality loss.\n"
        "4. For premium processing, tap *Batch Processing* to bundle multiple files as a ZIP archive."
    )
    if update.message:
        await update.message.reply_text(msg)
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg)

async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    
    if query.data == "menu_upload":
        await query.message.reply_text("🖼 Send the image you want to edit (JPG, PNG, WEBP, BMP):")
        return AWAITING_SINGLE_UPLOAD
        
    elif query.data == "menu_rotate":
        kb = [
            [InlineKeyboardButton("↩ 90° Left", callback_data="rot_90"),
             InlineKeyboardButton("↪ 90° Right", callback_data="rot_270")],
            [InlineKeyboardButton("🔄 180° Turn", callback_data="rot_180")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="go_home")]
        ]
        await query.edit_message_text("🔄 *Select Rotation Configuration:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return ROTATE_OPT
        
    elif query.data == "menu_flip":
        kb = [
            [InlineKeyboardButton("↔ Horizontally", callback_data="flp_horizontal")],
            [InlineKeyboardButton("↕ Vertically", callback_data="flp_vertical")],
            [InlineKeyboardButton("🔄 Both Directions", callback_data="flp_both")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="go_home")]
        ]
        await query.edit_message_text("↔️ *Select Flip Direction Option:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return FLIP_OPT

    elif query.data == "menu_resize":
        await query.message.reply_text("📏 Enter target Width in pixels (or send /skip to adjust by height only):")
        return RESIZE_OPT

    elif query.data == "menu_batch":
        context.user_data['batch_files'] = []
        await query.message.reply_text("📦 *Premium Batch Mode Active:*\n\nSend your images one by one. When you are finished uploading, send the command: /done", parse_mode="Markdown")
        return AWAITING_BATCH
        
    elif query.data == "go_home":
        await query.edit_message_text("Select an option below or send an image to get started:", reply_markup=get_main_menu())
        return MENU_CHOICE
        
    elif query.data == "menu_help":
        await help_cmd(update, context)
        return MENU_CHOICE

async def handle_single_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    photo = update.message.photo[-1] if update.message.photo else None
    doc = update.message.document if update.message.document else None
    
    file_id = None
    ext = ".png"
    
    if photo:
        file_id = photo.file_id
    elif doc and doc.mime_type.startswith("image/"):
        file_id = doc.file_id
        if doc.file_name:
            _, ext = os.path.splitext(doc.file_name)
    else:
        await update.message.reply_text("❌ Unsupported payload file type. Send a valid photo asset.")
        return AWAITING_SINGLE_UPLOAD
        
    utils.clear_user_cache(uid)
    tg_file = await context.bot.get_file(file_id)
    input_path = os.path.join(utils.TEMP_DIR, f"img_{uid}_source{ext}")
    await tg_file.download_to_drive(input_path)
    
    context.user_data['active_img'] = input_path
    context.user_data['active_ext'] = ext
    
    await update.message.reply_text("✅ Image received and cached. Choose a transformation using the menu buttons or use /start to refresh options.")
    return MENU_CHOICE

async def execute_rotation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    
    src = context.user_data.get('active_img')
    ext = context.user_data.get('active_ext', '.png')
    
    if not src or not os.path.exists(src):
        await query.message.reply_text("❌ No active image found. Please upload an image first using the main menu.")
        return MENU_CHOICE
        
    angle_map = {"rot_90": 90, "rot_180": 180, "rot_270": 270}
    angle = angle_map.get(query.data, 0)
    
    out = os.path.join(utils.TEMP_DIR, f"img_{uid}_output{ext}")
    success = image_processor.rotate_image(src, angle, out)
    
    if success and os.path.exists(out):
        with open(out, 'rb') as f:
            await query.message.reply_document(document=f, filename=f"rotated_{angle}{ext}")
        utils.clear_user_cache(uid)
    else:
        await query.message.reply_text("❌ Failed to process the image rotation.")
    return MENU_CHOICE

async def execute_flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    
    src = context.user_data.get('active_img')
    ext = context.user_data.get('active_ext', '.png')
    
    if not src or not os.path.exists(src):
        await query.message.reply_text("❌ No active image found. Please upload an image first.")
        return MENU_CHOICE
        
    direction = query.data.replace("flp_", "")
    out = os.path.join(utils.TEMP_DIR, f"img_{uid}_output{ext}")
    success = image_processor.flip_image(src, direction, out)
    
    if success and os.path.exists(out):
        with open(out, 'rb') as f:
            await query.message.reply_document(document=f, filename=f"flipped_{direction}{ext}")
        utils.clear_user_cache(uid)
    else:
        await query.message.reply_text("❌ Failed to flip the target file.")
    return MENU_CHOICE

async def execute_resize_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['r_width'] = None if text == "/skip" else int(text)
    await update.message.reply_text("📏 Now enter target Height in pixels (or send /skip to auto-calculate proportional ratio based on width):")
    return RESIZE_OPT

async def execute_resize_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    h_val = None if text == "/skip" else int(text)
    w_val = context.user_data.get('r_width')
    
    src = context.user_data.get('active_img')
    ext = context.user_data.get('active_ext', '.png')
    
    out = os.path.join(utils.TEMP_DIR, f"img_{uid}_output{ext}")
    success = image_processor.resize_image(src, w_val, h_val, out)
    
    if success and os.path.exists(out):
        with open(out, 'rb') as f:
            await update.message.reply_document(document=f, filename=f"resized_output{ext}")
        utils.clear_user_cache(uid)
    else:
        await update.message.reply_text("❌ Resizing execution block failure. Provide correct structural input configurations.")
    return MENU_CHOICE

async def handle_batch_uploads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    photo = update.message.photo[-1] if update.message.photo else None
    doc = update.message.document if update.message.document else None
    
    file_id = photo.file_id if photo else (doc.file_id if doc and doc.mime_type.startswith("image/") else None)
    
    if not file_id:
        await update.message.reply_text("❌ File ignored. Please provide valid image formats.")
        return AWAITING_BATCH
        
    idx = len(context.user_data.get('batch_files', []))
    tg_file = await context.bot.get_file(file_id)
    path = os.path.join(utils.TEMP_DIR, f"batch_{uid}_{idx}.png")
    await tg_file.download_to_drive(path)
    
    context.user_data['batch_files'].append(path)
    await update.message.reply_text(f"📝 Image #{idx + 1} queued. Send another or use /done to compile them.")
    return AWAITING_BATCH

async def compile_batch_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    files = context.user_data.get('batch_files', [])
    
    if not files:
        await update.message.reply_text("❌ Your batch queue is empty. Send images before invoking the closure execution flag command.")
        return MENU_CHOICE
        
    await update.message.reply_text("⚙️ Batch processing active: Flipping all queued images horizontally and bundling into a single ZIP archive...")
    
    processed_list = []
    for f in files:
        out = f.replace(".png", "_mod.png")
        if image_processor.flip_image(f, "horizontal", out):
            processed_list.append(out)
            
    zip_out = utils.create_batch_zip(uid, processed_list)
    
    with open(zip_out, 'rb') as zf:
        await update.message.reply_document(document=zf, filename="imagetwist_batch_archive.zip")
        
    utils.clear_user_cache(uid)
    return MENU_CHOICE

def main():
    if not TOKEN:
        print("Fatal Error: Missing BOT_TOKEN")
        return
        
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(menu_router, pattern="^menu_")
        ],
        states={
            MENU_CHOICE: [CallbackQueryHandler(menu_router, pattern="^(menu_|go_home)")],
            AWAITING_SINGLE_UPLOAD: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_single_upload)],
            ROTATE_OPT: [CallbackQueryHandler(execute_rotation, pattern="^rot_")],
            FLIP_OPT: [CallbackQueryHandler(execute_flip, pattern="^flp_")],
            RESIZE_OPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, execute_resize_width),
                CommandHandler("skip", execute_resize_width)
            ],
            AWAITING_BATCH: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_batch_uploads),
                CommandHandler("done", compile_batch_done)
            ]
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, execute_resize_final),
            CommandHandler("skip", execute_resize_final)
        ]
    )
    
    application.add_handler(conv_handler)
    print("ImageTwist Core Service running...")
    application.run_polling()

if __name__ == '__main__':
    main()

