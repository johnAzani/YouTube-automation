"""30-Night Scripture Protection Prayer Journal & Bedtime Declarations Builder.

Generates the official, majestic 34-page printable PDF companion:
  - Page 1: Midnight Sapphire & Gold Framing Cover
  - Page 2: Pastoral Introduction & The 4-Step Bedtime Watch
  - Pages 3-32: 30 Dedicated Nightly Scripture & Ruled Journaling Pages
  - Page 33: Bedside Emergency Scripture Shield (Panic, Insomnia, Grief)
  - Page 34: Closing Priestly Benediction & Ministry Partner Invitation

Strictly enforces:
  - $0.00 / month cost lock via ReportLab open-source engine
  - Zero mentions of personal names (editorial persona: The Secret Place)
  - Selar verified URL: https://selar.com/showlove/thesecretplace
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import REPO_ROOT

PRODUCTS_DIR = REPO_ROOT / "content" / "products"
OUTPUT_PDF_PATH = PRODUCTS_DIR / "30_night_prayer_journal.pdf"
SELAR_URL = os.environ.get("SELAR_STORE_URL", "https://selar.com/showlove/thesecretplace")


@dataclass(frozen=True)
class JournalNight:
    night_number: int
    theme: str
    scripture_text: str
    scripture_ref: str
    meditation: str
    declaration: str
    prayer: str
    prompt_surrender: str = "Burdens, worries, and names I surrender into God's hands tonight:"
    prompt_gratitude: str = "Mercies, answers to prayer, and blessings from today:"


NIGHTS_DATA: list[JournalNight] = [
    JournalNight(
        night_number=1,
        theme="The Shadow of the Almighty",
        scripture_text="He that dwelleth in the secret place of the most High shall abide under the shadow of the Almighty. I will say of the LORD, He is my refuge and my fortress: my God; in him will I trust.",
        scripture_ref="Psalm 91:1-2 (KJV)",
        meditation="The secret place is not a physical building or a distant mountain sanctuary; it is the posture of your heart turning toward God in the stillness of the evening. To abide under His shadow means you are close enough to the Father that His very presence covers you. Tonight, whatever anxiety, fatigue, or unresolved conflict accompanied your day, you do not have to carry it into your bed. Step under the canopy of the Almighty.",
        declaration="Tonight, I declare that my room is surrounded by the presence of God. The Lord is my personal refuge and unshakable fortress. I release all fear, anxiety, and sleeplessness. I dwell in the secret place, and under His wings I shall rest in perfect peace. Amen.",
        prayer="Heavenly Father, as darkness falls across the earth, I draw near to Your secret pavilion. Forgive every shortcoming of this day, quiet the storm within my thoughts, and shelter my soul under Your unfailing wings. In Jesus' name, Amen.",
    ),
    JournalNight(
        night_number=2,
        theme="Deliverance From Terror by Night",
        scripture_text="Thou shalt not be afraid for the terror by night; nor for the arrow that flieth by day; Nor for the pestilence that walketh in darkness; nor for the destruction that wasteth at noonday.",
        scripture_ref="Psalm 91:5-6 (KJV)",
        meditation="Nighttime often amplifies fear. Shadows seem deeper, silence feels heavier, and the enemy attempts to weaponize the quiet against your mind. Yet God's ancient promise remains unbroken: you will not fear the terror by night. The terrors of darkness possess no authority over an atmosphere saturated by God's covenant. You are not unprotected; you are fortified.",
        declaration="I will not fear the terror by night. No weapon formed against my peace, my health, or my sleep shall prosper. Every intrusive thought is silenced by the blood of Jesus. My home is a holy sanctuary of rest.",
        prayer="Lord of Hosts, command Your peace to stand watch over every door, window, and corner of my home. Cast out all demonic dread and midnight anxiety. Fill my sleeping hours with tranquility and divine dreams. Amen.",
    ),
    JournalNight(
        night_number=3,
        theme="Angelic Guardians Stationed at Your Bed",
        scripture_text="For he shall give his angels charge over thee, to keep thee in all thy ways. They shall bear thee up in their hands, lest thou dash thy foot against a stone.",
        scripture_ref="Psalm 91:11-12 (KJV)",
        meditation="While your physical eyes close in sleep, the spiritual realm remains active. God does not leave you unguarded. He dispatches ministering spirits—mighty angels who excel in strength—to surround your dwelling place. Sleep is an act of trust where you concede control to the Creator, knowing heavenly guardians stand on post until the dawn.",
        declaration="God has given His angels charge over me and my household tonight. Heavenly protectors encamp around my bed. I am secure, I am defended, and no plague shall come near my dwelling place.",
        prayer="Sovereign Father, thank You for the unseen army of angels that encamps around those who fear You. Let Your holy messengers guard my spirit, mind, and body throughout this night, preserving my life until morning. Amen.",
    ),
    JournalNight(
        night_number=4,
        theme="Green Pastures and Restored Souls",
        scripture_text="The LORD is my shepherd; I shall not want. He maketh me to lie down in green pastures: he leadeth me beside the still waters. He restoreth my soul.",
        scripture_ref="Psalm 23:1-3 (KJV)",
        meditation="Sheep cannot lie down when they are fearful, agitated, hungry, or burdened by parasites. They only rest when the Shepherd is present in the field. Tonight, the Good Shepherd invites you to lay down your striving. He has provided all you need for this day. Drink deeply from the still waters of His grace and let Him gently reconstruct your weary soul.",
        declaration="The Lord is my Shepherd; I lack no good thing. Tonight, He makes me lie down in green pastures and leads me beside still waters. My soul is being supernaturally restored while I rest.",
        prayer="O Shepherd of Israel, I lay down my heavy burdens at Your feet. Quench the thirst of my dry spirit, quiet the racing gears of my mind, and restore the joy of my salvation as I sleep under Your watchful eye. Amen.",
    ),
    JournalNight(
        night_number=5,
        theme="Fearless in the Dark Valley",
        scripture_text="Yea, though I walk through the valley of the shadow of death, I will fear no evil: for thou art with me; thy rod and thy staff they comfort me.",
        scripture_ref="Psalm 23:4 (KJV)",
        meditation="Notice the Psalmist writes through the valley, not into it to remain there. A shadow may look intimidating, but a shadow has no physical substance; it cannot harm you. Furthermore, a shadow requires light to exist. Even in your darkest season of grief, sickness, or uncertainty, the Light of the World walks beside you. You are never walking alone.",
        declaration="Even in the darkest valley, I will fear no evil, for God is with me. His rod defends me; His staff guides me. This valley is not my permanent residence; it is only a passage into His victory.",
        prayer="Comforting God, when shadows of sadness or fear try to engulf my mind tonight, remind me of Your closeness. Let the assurance of Your presence dispel every dark thought. I take comfort in Your loving protection. Amen.",
    ),
    JournalNight(
        night_number=6,
        theme="Goodness and Mercy Pursuing You",
        scripture_text="Surely goodness and mercy shall follow me all the days of my life: and I will dwell in the house of the LORD for ever.",
        scripture_ref="Psalm 23:6 (KJV)",
        meditation="In ancient Hebrew, the word translated 'follow' (radaph) means to pursue, hunt down, or chase with passion. God's goodness and loyal covenant mercy are not casually trailing behind you—they are relentlessly pursuing you. Even when you feel inadequate or tired, God's mercy is running after you to cover your mistakes and bless your tomorrows.",
        declaration="God's goodness and mercy are pursuing me tonight and every day of my life. My past is forgiven; my future is established in Christ. I go to sleep surrounded by lovingkindness.",
        prayer="Lord of Unfailing Love, thank You that Your mercies are new every single morning. I forgive those who hurt me today and receive Your cleansing mercy for my own soul. Let goodness and peace crown my slumber tonight. Amen.",
    ),
    JournalNight(
        night_number=7,
        theme="The Guardian Who Never Slumbers",
        scripture_text="I will lift up mine eyes unto the hills, from whence cometh my help. My help cometh from the LORD, which made heaven and earth. He will not suffer thy foot to be moved: he that keepeth thee will not slumber.",
        scripture_ref="Psalm 121:1-3 (KJV)",
        meditation="Humans grow weary; our bodies demand rest, and our eyelids become heavy. But the Creator of the galaxies never grows faint or tired. You can safely close your eyes tonight because God is staying awake. There is no shift change in heaven; there is no moment where your life is left unattended. Put your concerns to bed because your Guardian is on watch.",
        declaration="My help comes from the Lord, the Maker of heaven and earth. He will not let my foot slip. My Keeper does not slumber or sleep, so I can rest in absolute peace and confidence.",
        prayer="Faithful Keeper, into Your tireless hands I entrust my family, my home, and my tomorrows. Because You never sleep, I don't need to stay awake worrying. Grant me the deep, healing sleep of the beloved. Amen.",
    ),
    JournalNight(
        night_number=8,
        theme="Preserved From All Evil",
        scripture_text="The LORD shall preserve thee from all evil: he shall preserve thy soul. The LORD shall preserve thy going out and thy coming in from this time forth, and even for evermore.",
        scripture_ref="Psalm 121:7-8 (KJV)",
        meditation="Preservation means God sustains the integrity of your soul even while you walk in a fallen world. Evil may swirl around the culture, but God has drawn a holy boundary line around your life. Tonight, as you transition from daytime activity to nighttime stillness, know that your coming in is just as blessed and preserved as your going out.",
        declaration="The Lord preserves my soul from all evil. He guards my coming in and my going out from this night forth and forevermore. I am sealed, defended, and preserved by His grace.",
        prayer="Preserving God, build a hedge of fire around my life and loved ones tonight. Shield us from sickness, accidents, spiritual attacks, and distress. Let Your peace rule like an umpire in my heart. Amen.",
    ),
    JournalNight(
        night_number=9,
        theme="In Peace I Will Lie Down and Sleep",
        scripture_text="I will both lay me down in peace, and sleep: for thou, LORD, only makest me dwell in safety.",
        scripture_ref="Psalm 4:8 (KJV)",
        meditation="King David penned this psalm while facing tremendous pressure and betrayal, yet he declared he would lie down and sleep. Peace is not the absence of trouble; it is the presence of God within the trouble. True safety does not come from locks, bank accounts, or human alliances—it comes from the Lord alone. Surrender your need to solve tomorrow's problems tonight.",
        declaration="In peace I will lie down, and in peace I will sleep. The Lord alone makes me dwell in safety. I disconnect from the noise of the world and anchor my soul in divine tranquility.",
        prayer="Lord of Peace, quiet my heart from the disputes, tasks, and demands of the day. Release tension from my body and racing thoughts from my mind. I breathe in Your peace and breathe out all anxious striving. Amen.",
    ),
    JournalNight(
        night_number=10,
        theme="The Lord is My Light and Salvation",
        scripture_text="The LORD is my light and my salvation; whom shall I fear? the LORD is the strength of my life; of whom shall I be afraid?",
        scripture_ref="Psalm 27:1 (KJV)",
        meditation="When light enters a room, darkness does not negotiate—it flees instantly. The Lord is not just a light bearer; He is your light. Whatever dark questions, diagnosis, or intimidating circumstances confronted you today, they shrink to nothing in comparison to the radiant sovereignty of God. Fear is bankrupt before the strength of the Lord.",
        declaration="The Lord is my light and my salvation; I will fear no one. The Lord is the stronghold of my life; of whom shall I be afraid? Darkness has no power over my mind or home.",
        prayer="Father, illuminate the dark places of my thinking with the truth of Your Word. Where anxiety whispers defeat, let Your voice declare victory. I rest beneath the beacon of Your eternal love tonight. Amen.",
    ),
    JournalNight(
        night_number=11,
        theme="Hidden in the Secret Pavilion",
        scripture_text="For in the time of trouble he shall hide me in his pavilion: in the secret of his tabernacle shall he hide me; he shall set me up upon a rock.",
        scripture_ref="Psalm 27:5 (KJV)",
        meditation="In ancient warfare, the general's pavilion was pitched in the safest, most fortified center of the army's encampment. To be hidden in God's pavilion means God places you in the inner sanctuary of His personal protection. In times of emotional or physical storm, God takes you into His private quarters and lifts your feet onto the rock of Christ.",
        declaration="I am hidden in the secret pavilion of the Most High. The enemy cannot locate my peace, for my life is hidden with Christ in God. My feet stand firmly upon the Rock.",
        prayer="Lord, hide me in the sacred canopy of Your presence tonight. Shield me from the strife of tongues, the accusations of the adversary, and the fatigue of the world. Set my mind upon Your rock. Amen.",
    ),
    JournalNight(
        night_number=12,
        theme="A Very Present Help in Trouble",
        scripture_text="God is our refuge and strength, a very present help in trouble. Therefore will not we fear, though the earth be removed, and though the mountains be carried into the midst of the sea.",
        scripture_ref="Psalm 46:1-2 (KJV)",
        meditation="God is not a distant, reluctant deity who arrives late to emergencies. He is 'a very present help'—immediately accessible, intimately acquainted with your pain, and actively working even when circumstances seem chaotic. Even if the foundations of your earthly life seem shaken, God remains the immovable bedrock of your existence.",
        declaration="God is my refuge and my strength, an ever-present help in trouble. I will not fear, even if mountains tremble. God is in the midst of my life; I shall not be moved.",
        prayer="Almighty God, thank You that You are closer to me than my very breath. When overwhelming waves threaten to drown my peace, be my anchor. I place every unresolved situation into Your capable hands tonight. Amen.",
    ),
    JournalNight(
        night_number=13,
        theme="Be Still, and Know That I Am God",
        scripture_text="Be still, and know that I am God: I will be exalted among the heathen, I will be exalted in the earth. The LORD of hosts is with us; the God of Jacob is our refuge. Selah.",
        scripture_ref="Psalm 46:10-11 (KJV)",
        meditation="The Hebrew command for 'be still' (raphah) literally translates to 'let go, drop your hands, cease striving.' It is a call to stop fighting God's battles with human weapons. When you let go, God takes over. Rest is an act of spiritual warfare where you honor God's supremacy by stepping down from managing the universe and allowing Him to be God.",
        declaration="I drop my hands, I cease striving, and I rest. I know that the Lord is God, and He reigns supreme over every detail of my life. The Lord of Hosts is with me; my victory is secure.",
        prayer="Lord Jesus, I silence the restless voices of panic and control. Teach my soul the holy art of stillness. As I lay in bed, I let go of what I cannot control and worship You as Lord over all. Amen.",
    ),
    JournalNight(
        night_number=14,
        theme="The Encamping Angel of the Lord",
        scripture_text="The angel of the LORD encampeth round about them that fear him, and delivereth them. O taste and see that the LORD is good: blessed is the man that trusteth in him.",
        scripture_ref="Psalm 34:7-8 (KJV)",
        meditation="Notice the word 'encampeth.' The angel of the Lord doesn't just pass by on a temporary reconnaissance mission; He pitches a defensive military circle around your life. If you could see with spiritual eyes tonight, you would witness the glory of God forming a ring of divine fire around your bedroom. You are surrounded by heaven's favor.",
        declaration="The angel of the Lord encamps round about me tonight. I am delivered from every entrapment. I taste and see that the Lord is good; blessed am I because I put my trust in Him.",
        prayer="Heavenly Father, open the eyes of my heart to know that those who are with me are greater than those in the world. I rest securely within the circle of Your holy protection tonight. Amen.",
    ),
    JournalNight(
        night_number=15,
        theme="The Shield That Lifts My Head",
        scripture_text="Thou, O LORD, art a shield for me; my glory, and the lifter up of mine head. I cried unto the LORD with my voice, and he heard me out of his holy hill... I laid me down and slept; I awaked; for the LORD sustained me.",
        scripture_ref="Psalm 3:3-5 (KJV)",
        meditation="When life knocks you down, the natural reaction is to hang your head in shame, defeat, or grief. But God is not only your 360-degree shield—He is the lifter of your head. He lifts your chin to look into His eyes of grace. David slept peacefully while thousands of adversaries pursued him, because he knew that sleep was sustained by the grace of God.",
        declaration="The Lord is a shield around me, my glory, and the lifter of my head. I cry out to God, and He hears me. I lay down to sleep in peace, and I will awake, for the Lord sustains me.",
        prayer="Father, lift the heaviness from my heart tonight. Where condemnation or regret hung my head today, let Your grace lift my spirit. Thank You for sustaining my heartbeats while I sleep. Amen.",
    ),
    JournalNight(
        night_number=16,
        theme="Counsel in the Night Seasons",
        scripture_text="I will bless the LORD, who hath given me counsel: my reins also instruct me in the night seasons. I have set the LORD always before me: because he is at my right hand, I shall not be moved.",
        scripture_ref="Psalm 16:7-8 (KJV)",
        meditation="In biblical understanding, the 'reins' refer to the deep inner conscience and heart. While your conscious mind rests in sleep, God's Spirit continues to counsel, heal, and instruct your innermost being. The night season is not lost time; it is a season of holy recalibration where God realigns your thoughts with His kingdom wisdom.",
        declaration="The Lord gives me wisdom and counsels my heart during the night. I set the Lord always before me; because He is at my right hand, I will never be shaken. My mind is filled with divine light.",
        prayer="Holy Spirit, speak to my subconscious thoughts as I rest. Cleanse my mind of toxic narratives, grant me godly solutions to difficult decisions, and awaken me with fresh divine clarity. Amen.",
    ),
    JournalNight(
        night_number=17,
        theme="My Rock, My Fortress, My Deliverer",
        scripture_text="The LORD is my rock, and my fortress, and my deliverer; my God, my strength, in whom I will trust; my buckler, and the horn of my salvation, and my high tower.",
        scripture_ref="Psalm 18:2 (KJV)",
        meditation="Consider David's military imagery: a rock is immovable underfoot; a fortress provides thick walls against arrows; a buckler absorbs direct blows; a high tower gives perspective above the battlefield. God is not merely one defense; He is your complete multi-layered security system. Rest tonight within the impregnable walls of His love.",
        declaration="The Lord is my Rock, my Fortress, and my Deliverer. My God is my strength in whom I trust. I run into His high tower tonight and I am safe from every spiritual storm.",
        prayer="Lord Jesus, You are my eternal sanctuary. When worldly circumstances shift like sand, You remain my solid rock. Guard my thoughts and emotions tonight from the arrows of the enemy. Amen.",
    ),
    JournalNight(
        night_number=18,
        theme="Committing My Spirit to His Hand",
        scripture_text="In thee, O LORD, do I put my trust; let me never be ashamed: deliver me in thy righteousness... Into thine hand I commit my spirit: thou hast redeemed me, O LORD God of truth.",
        scripture_ref="Psalm 31:1, 5 (KJV)",
        meditation="These sacred words of Psalm 31:5 became the traditional bedtime prayer of Jewish children, and they were the final words of Jesus Christ upon the Cross. Committing your spirit into God's hands is the ultimate act of bedtime trust. God's hands formed the universe, carved the stars, and hold you with tenderness. Your life is safer in His hands than in your own.",
        declaration="Into Your hands, Father, I commit my spirit, my family, and my future. You have redeemed me, O Lord God of truth. I rest securely in the palm of Your everlasting hands.",
        prayer="Loving Father, I release my grasp on life's problems and place myself into Your nail-pierced hands. You are faithful to preserve what I have committed unto You. Let Your peace flood my soul. Amen.",
    ),
    JournalNight(
        night_number=19,
        theme="Rest in the Lord and Wait Patiently",
        scripture_text="Trust in the LORD, and do good; so shalt thou dwell in the land, and verily thou shalt be fed. Delight thyself also in the LORD; and he shall give thee the desires of thine heart. Rest in the LORD, and wait patiently for him.",
        scripture_ref="Psalm 37:3-4, 7 (KJV)",
        meditation="Impatience and anxiety are twin thieves of sleep. We lie awake worrying about outcomes that have not yet occurred and timelines we cannot rush. Scripture commands us: 'Rest in the Lord, and wait patiently for Him.' God's delays are not denials; His timing is masterfully orchestrated. While you rest tonight, God is already arranging tomorrow's divine appointments.",
        declaration="I delight myself in the Lord, and I commit my way to Him. I rest in God and wait patiently for His perfect timing. He is orchestrating blessings and answers on my behalf right now.",
        prayer="Lord, deliver me from the anxiety of rushing ahead of Your will. Teach me to be patient and content in Your presence. As I sleep, let Your Holy Spirit mature my faith and deepen my trust. Amen.",
    ),
    JournalNight(
        night_number=20,
        theme="Remembering God Upon My Bed",
        scripture_text="My soul shall be satisfied as with marrow and fatness; and my mouth shall praise thee with joyful lips: When I remember thee upon my bed, and meditate on thee in the night watches. Because thou hast been my help, therefore in the shadow of thy wings will I rejoice.",
        scripture_ref="Psalm 63:5-7 (KJV)",
        meditation="If you awaken in the middle of the night, do not allow panic or insomnia to dominate your consciousness. Turn your midnight wakefulness into a sacred altar of remembrance. Rehearse the times God came through for you in the past, recount His faithfulness, and meditate on His attributes. When you turn midnight restlessness into praise, anxiety loses its foothold.",
        declaration="I meditate on God during the night watches. Because He has been my help, I rejoice under the shadow of His wings. My soul is satisfied with His goodness, and my sleep is peaceful.",
        prayer="Lord God, when I awaken in the night, let my first reflex be praise rather than panic. Fill my midnight thoughts with memories of Your kindness and songs of deliverance. Amen.",
    ),
    JournalNight(
        night_number=21,
        theme="Darkness is as Light to Him",
        scripture_text="If I say, Surely the darkness shall cover me; even the night shall be light about me. Yea, the darkness hideth not from thee; but the night shineth as the day: the darkness and the light are both alike to thee.",
        scripture_ref="Psalm 139:11-12 (KJV)",
        meditation="While darkness blinds human sight and fuels fearful imaginations, it is completely transparent to God. To Him, the deepest midnight shines as brilliantly as midday sun. God sees what is happening in secret, He sees the roots of your emotional pain, and He is working in the dark places of your life. You are never lost or forgotten in the dark.",
        declaration="No darkness can hide me from God's presence. Even the night is light around me. Darkness and light are both alike to my Father. His hand leads me and His right hand holds me fast.",
        prayer="All-Seeing Father, thank You that the darkness of this night holds no mystery or terror for You. Shine the light of Your countenance into every dark corner of my heart, driving away all loneliness. Amen.",
    ),
    JournalNight(
        night_number=22,
        theme="When You Lie Down, Sleep is Sweet",
        scripture_text="When thou liest down, thou shalt not be afraid: yea, thou shalt lie down, and thy sleep shall be sweet. Be not afraid of sudden fear, neither of the desolation of the wicked, when it cometh. For the LORD shall be thy confidence.",
        scripture_ref="Proverbs 3:24-26 (KJV)",
        meditation="Sweet sleep is not merely physical exhaustion; it is the spiritual fruit of a conscience cleansed by grace and a mind anchored in divine wisdom. God does not intend for your nights to be tormented by dread, nightmares, or recurring regrets. He promises that when you keep His wisdom, your sleep shall be sweet, restorative, and refreshing.",
        declaration="When I lie down tonight, I shall not be afraid. Yes, I will lie down, and my sleep shall be sweet. God's wisdom guards my steps, and His peace envelops my resting hours.",
        prayer="Lord of Wisdom, wash my mind with the water of Your Word. Remove all bitter thoughts, unresolved offenses, and heavy regrets from my heart. Grant me the sweet, restorative rest You promised to Your children. Amen.",
    ),
    JournalNight(
        night_number=23,
        theme="Kept in Perfect Peace",
        scripture_text="Thou wilt keep him in perfect peace, whose mind is stayed on thee: because he trusteth in thee. Trust ye in the LORD for ever: for in the LORD JEHOVAH is everlasting strength.",
        scripture_ref="Isaiah 26:3-4 (KJV)",
        meditation="In Hebrew, the phrase 'perfect peace' is shalom shalom—peace multiplied upon peace, double peace, complete wholeness with nothing missing and nothing broken. The condition is simple yet profound: fix your mind upon the Lord rather than the storm. Fix your eyes upon His promises tonight, and His everlasting strength will garrison your heart.",
        declaration="My mind is stayed on the Lord, and He keeps me in perfect peace. I trust in Jehovah forever, for in Him is everlasting strength. My thoughts are settled in Christ.",
        prayer="Prince of Peace, I bring every wandering, anxious thought into captivity to the obedience of Christ. Fasten my focus onto Your goodness. Let Your double peace guard my heart and mind through Christ Jesus. Amen.",
    ),
    JournalNight(
        night_number=24,
        theme="Upholding You With His Right Hand",
        scripture_text="Fear thou not; for I am with thee: be not dismayed; for I am thy God: I will strengthen thee; yea, I will help thee; yea, I will uphold thee with the right hand of my righteousness.",
        scripture_ref="Isaiah 41:10 (KJV)",
        meditation="Notice the fivefold promise of God in this single verse: 1. I am with you; 2. I am your God; 3. I will strengthen you; 4. I will help you; 5. I will uphold you. You do not have to muster the strength to hold onto God tonight; God's righteous right hand is holding onto you. You are carried by omnipotence.",
        declaration="I will not fear, for God is with me. I will not be dismayed, for He is my God. He strengthens me, helps me, and upholds me with His righteous right hand. I am safe in His grasp.",
        prayer="Heavenly Father, when I feel weak, overwhelmed, or tired from life's battles, remind me that You are upholding me. I cease my struggle and lean into Your everlasting arms tonight. Amen.",
    ),
    JournalNight(
        night_number=25,
        theme="Rest for the Weary Soul",
        scripture_text="Come unto me, all ye that labour and are heavy laden, and I will give you rest. Take my yoke upon you, and learn of me; for I am meek and lowly in heart: and ye shall find rest unto your souls. For my yoke is easy, and my burden is light.",
        scripture_ref="Matthew 11:28-30 (KJV)",
        meditation="Religion demands heavy performance, but Jesus offers a divine trade: bring Him your exhaustion, guilt, and burnout, and He gives you rest. The rest Jesus provides is not just physical relaxation—it is deep, soul-level rest that heals emotional fractures and dissolves anxiety. Unyoke yourself from the world's expectations and enter the rest of Christ.",
        declaration="I come to Jesus tonight and lay down my heavy burdens. I take His easy yoke upon me. In Christ, my soul finds profound rest, healing, and peace. His burden is light and His grace is sufficient.",
        prayer="Lord Jesus, I take off the heavy armor of self-justification, worry, and striving. I lay my weary soul at Your feet. Teach me Your gentle ways, and let Your restorative rest saturate my spirit tonight. Amen.",
    ),
    JournalNight(
        night_number=26,
        theme="My Peace I Give Unto You",
        scripture_text="Peace I leave with you, my peace I give unto you: not as the world giveth, give I unto you. Let not your heart be troubled, neither let it be afraid.",
        scripture_ref="John 14:27 (KJV)",
        meditation="The peace of the world depends entirely on external conditions—money in the bank, health in the body, quiet in the home. But the peace Jesus gives is an internal fortress that thrives even in the midst of turmoil. It was on the eve of His crucifixion that Jesus bequeathed His peace to His disciples. His peace is an unbreakable inheritance that the world cannot give and cannot take away.",
        declaration="I receive the supernatural peace of Jesus Christ tonight. My heart is not troubled, neither is it afraid. Christ's peace reigns supreme in my home, my family, and my sleeping hours.",
        prayer="Lord Jesus, thank You for bequeathing Your peace to me. I refuse the counterfeits of worldly worry and receive Your divine tranquility. Expel every spirit of fear and quiet my soul with Your love. Amen.",
    ),
    JournalNight(
        night_number=27,
        theme="The Peace That Guards Heart and Mind",
        scripture_text="Be careful for nothing; but in every thing by prayer and supplication with thanksgiving let your requests be made known unto God. And the peace of God, which passeth all understanding, shall keep your hearts and minds through Christ Jesus.",
        scripture_ref="Philippians 4:6-7 (KJV)",
        meditation="The Greek word for 'keep' (phroureo) is a military term describing a detachment of armed soldiers garrisoned around a city gate to prevent intrusion. When you transform your worries into prayers combined with gratitude, the peace of God stands sentry at the gates of your heart and the doorways of your thoughts. Anxiety is refused entry.",
        declaration="I am anxious for nothing. In everything, with prayer and thanksgiving, I make my requests known to God. The peace of God, which surpasses all human understanding, guards my heart and mind tonight.",
        prayer="Faithful God, I hand over every petition, concern, and unanswered question to You with a grateful heart. Post Your heavenly garrison of peace around my mind tonight, blocking every lie of the enemy. Amen.",
    ),
    JournalNight(
        night_number=28,
        theme="Power, Love, and a Sound Mind",
        scripture_text="For God hath not given us the spirit of fear; but of power, and of love, and of a sound mind.",
        scripture_ref="2 Timothy 1:7 (KJV)",
        meditation="Notice the profound truth of this scripture: fear is not merely an emotion; it is an unholy spirit that does not originate from God. Whenever fear, panic, or confusion attempts to dominate your midnight thoughts, you can trace its origin and reject it with authority. God has endowed you with power over darkness, love that casts out fear, and a sound, disciplined, restful mind.",
        declaration="God has not given me a spirit of fear, but of power, of love, and of a sound mind. I renounce all night terrors and racing thoughts. My mind is clear, peaceful, and anchored in truth.",
        prayer="Almighty Father, by the authority of Your Word, I reject every spirit of torment, fear, and panic. Clothe my thoughts in Your power, fill my emotions with Your love, and grant me a calm, sound mind as I sleep. Amen.",
    ),
    JournalNight(
        night_number=29,
        theme="Casting All Your Care Upon Him",
        scripture_text="Humble yourselves therefore under the mighty hand of God, that he may exalt you in due time: Casting all your care upon him; for he careth for you.",
        scripture_ref="1 Peter 5:6-7 (KJV)",
        meditation="The word 'casting' denotes a decisive, forceful throw—like hurling a heavy net away from yourself into the ocean. Carrying the burdens of life yourself is an act of subtle pride; casting them onto God is true humility. You were never designed to carry the crushing weight of tomorrow. Throw every heavy care into the arms of the Father who cares for you with infinite affection.",
        declaration="Tonight, I cast every single care, burden, and anxiety upon the Lord, for He cares for me with boundless love. I will not carry what God has promised to carry for me. I am light and free.",
        prayer="Abba Father, You know every detail that weighs down my spirit tonight. I deliberately cast these burdens off my shoulders and into Your capable hands. Thank You that You never grow weary of caring for me. Amen.",
    ),
    JournalNight(
        night_number=30,
        theme="The Priestly Benediction of Peace",
        scripture_text="The LORD bless thee, and keep thee: The LORD make his face shine upon thee, and be gracious unto thee: The LORD lift up his countenance upon thee, and give thee peace.",
        scripture_ref="Numbers 6:24-26 (KJV)",
        meditation="For thousands of years, this sacred Aaronic blessing has been spoken over God's covenant people. To have God's face shine upon you means His favor, delight, and fatherly pleasure are turned toward you. To have Him lift up His countenance means He looks you in the eye with undivided love and bestows His eternal shalom. You are blessed, kept, and guarded forever.",
        declaration="The Lord blesses me and keeps me. The Lord makes His face shine upon me and is gracious to me. The Lord lifts up His countenance upon me and grants me His permanent, unshakable peace. Amen.",
        prayer="Eternal Lord, let this ancient blessing rest upon my head, my home, my family, and my generations tonight. May Your peace cover my slumber and awake me to fresh mercies tomorrow morning. In the mighty name of Jesus, Amen.",
    ),
]


class JournalNumberedCanvas(canvas.Canvas):
    """Two-pass canvas adding running headers, footers, and the deep sapphire cover."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            w, h = letter

            if self._pageNumber == 1:
                # Cover Page Design
                self.saveState()
                # Deep Midnight Sapphire Background
                self.setFillColor(colors.HexColor("#0b1329"))
                self.rect(0, 0, w, h, fill=1, stroke=0)

                # Gold Outer & Inner Frame
                self.setStrokeColor(colors.HexColor("#d97706"))
                self.setLineWidth(3)
                self.rect(28, 28, w - 56, h - 56, fill=0, stroke=1)

                self.setStrokeColor(colors.HexColor("#fde68a"))
                self.setLineWidth(1)
                self.rect(34, 34, w - 68, h - 68, fill=0, stroke=1)

                # Corner Accents
                self.setLineWidth(2)
                self.setStrokeColor(colors.HexColor("#f59e0b"))
                for cx, cy in [(34, 34), (w - 34, 34), (34, h - 34), (w - 34, h - 34)]:
                    self.circle(cx, cy, 3, fill=1, stroke=1)

                # Cover Typography
                self.setFillColor(colors.HexColor("#93c5fd"))
                self.setFont("Helvetica-Bold", 12)
                self.drawCentredString(w / 2, h - 140, "THE SECRET PLACE PRESENTS")

                self.setFillColor(colors.white)
                self.setFont("Helvetica-Bold", 26)
                self.drawCentredString(w / 2, h - 200, "30-NIGHT SCRIPTURE")
                self.drawCentredString(w / 2, h - 235, "PROTECTION PRAYER JOURNAL")

                self.setFillColor(colors.HexColor("#fbbf24"))
                self.setFont("Helvetica-Bold", 14)
                self.drawCentredString(w / 2, h - 270, "& BEDTIME DECLARATIONS")

                # Decorative Divider
                self.setStrokeColor(colors.HexColor("#d97706"))
                self.setLineWidth(1.5)
                self.line(w / 2 - 110, h - 300, w / 2 + 110, h - 300)

                # Subtitle
                self.setFillColor(colors.HexColor("#e2e8f0"))
                self.setFont("Helvetica", 11)
                self.drawCentredString(w / 2, h - 335, "A Liturgical Bedside Sanctuary for Anxious Hearts,")
                self.drawCentredString(w / 2, h - 355, "Restoring Sleep Under the Shadow of the Almighty")

                # Scripture Box (Psalm 4:8)
                self.setFillColor(colors.HexColor("#1e293b"))
                self.setStrokeColor(colors.HexColor("#3b82f6"))
                self.setLineWidth(1)
                self.roundRect(w / 2 - 180, h - 490, 360, 95, 10, fill=1, stroke=1)

                self.setFillColor(colors.HexColor("#fde68a"))
                self.setFont("Helvetica-Bold", 10.5)
                self.drawCentredString(w / 2, h - 430, '"In peace I will both lie down and sleep;')
                self.drawCentredString(w / 2, h - 448, 'for you alone, O LORD, make me dwell in safety."')
                self.setFillColor(colors.HexColor("#94a3b8"))
                self.setFont("Helvetica-Oblique", 9.5)
                self.drawCentredString(w / 2, h - 470, "— Psalm 4:8 (KJV)")

                # Deliverable Bullets
                self.setFillColor(colors.HexColor("#cbd5e1"))
                self.setFont("Helvetica", 9.5)
                self.drawCentredString(w / 2, h - 540, "• 30 Canonical Scripture Meditations • Daily Bedtime Spoken Declarations •")
                self.drawCentredString(w / 2, h - 560, "• Guided Evening Surrender Prayers • Bedside Ruled Peace Journaling •")
                self.drawCentredString(w / 2, h - 580, "• Emergency Bedside Scripture Shield for Panic, Grief, and Insomnia •")

                # Sanctuary Link
                self.setFillColor(colors.HexColor("#94a3b8"))
                self.setFont("Helvetica", 8.5)
                self.drawCentredString(w / 2, 80, "Daily Scripture & Evening Prayer Sanctuary · Public Domain KJV Scripture")
                self.setFillColor(colors.HexColor("#60a5fa"))
                self.drawCentredString(w / 2, 60, f"{SELAR_URL} · @TheSecretPlace")
                self.restoreState()
            else:
                # Running Header (Pages 2+)
                self.saveState()
                self.setFont("Helvetica-Bold", 8)
                self.setFillColor(colors.HexColor("#64748b"))
                self.drawString(36, h - 28, "THE SECRET PLACE · 30-NIGHT BEDTIME SCRIPTURE PRAYER JOURNAL")
                self.setStrokeColor(colors.HexColor("#e2e8f0"))
                self.setLineWidth(0.5)
                self.line(36, h - 34, w - 36, h - 34)

                # Running Footer (Pages 2+)
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#64748b"))
                self.line(36, 32, w - 36, 32)
                self.drawString(36, 20, "Daily Scripture & Evening Prayer Sanctuary")
                self.drawRightString(w - 36, 20, f"Page {self._pageNumber} of {num_pages}")
                self.drawCentredString(w / 2, 20, f"{SELAR_URL}")
                self.restoreState()

            super().showPage()
        super().save()


def build_prayer_journal_pdf(out_path: Path = OUTPUT_PDF_PATH) -> Path:
    """Build the complete 34-page printable Prayer Journal PDF."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Document Geometry (Letter size, 0.5-inch margins)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=42,
    )

    styles = getSampleStyleSheet()

    # Typography Styles
    title_style = ParagraphStyle(
        "NightHeader",
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor("#0f172a"),
    )
    theme_style = ParagraphStyle(
        "NightTheme",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#2563eb"),
        textTransform="uppercase",
    )
    scripture_style = ParagraphStyle(
        "Scripture",
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )
    scripture_ref_style = ParagraphStyle(
        "ScriptureRef",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#b45309"),
        alignment=2,
    )
    meditation_style = ParagraphStyle(
        "Meditation",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.2,
        textColor=colors.HexColor("#334155"),
    )
    dec_style = ParagraphStyle(
        "Declaration",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12.2,
        textColor=colors.HexColor("#1e3a8a"),
    )
    prayer_style = ParagraphStyle(
        "Prayer",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    )
    label_style = ParagraphStyle(
        "Label",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
        textTransform="uppercase",
    )
    prompt_style = ParagraphStyle(
        "SubPrompt",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    # ---------------------------------------------------------
    # PAGE 1: COVER (Handled by JournalNumberedCanvas)
    # ---------------------------------------------------------
    story.append(Spacer(1, 100))
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 2: PASTORAL INTRODUCTION & THE 4-STEP BEDTIME WATCH
    # ---------------------------------------------------------
    intro_h1 = ParagraphStyle("IntroH1", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"))
    intro_h2 = ParagraphStyle("IntroH2", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=colors.HexColor("#2563eb"))
    intro_body = ParagraphStyle("IntroBody", fontName="Helvetica", fontSize=8.8, leading=13, textColor=colors.HexColor("#334155"))

    story.append(Paragraph("Welcome to The Secret Place", intro_h1))
    story.append(Spacer(1, 3))
    story.append(Paragraph("A SANCTUARY FOR RESTORING WEARY SOULS", intro_h2))
    story.append(Spacer(1, 10))

    intro_p1 = (
        "Beloved friend, if you are holding this journal, chances are your days are filled with noise, "
        "demands, and the relentless pressure of a restless world. The hours before sleep are often the most "
        "vulnerable moments of the human soul. When the lights go out and daytime distractions cease, anxieties "
        "whisper their loudest lies. Yet God designed the evening not as a battlefield of dread, but as an altar of peace."
    )
    story.append(Paragraph(intro_p1, intro_body))
    story.append(Spacer(1, 8))

    intro_p2 = (
        "This 30-Night Scripture Protection Prayer Journal is your bedtime companion. For thirty consecutive nights, "
        "you are invited to step out of the storm of self-reliance and step into the secret place of the Most High. "
        "Each night anchors your heart in public-domain scripture, provides pastoral reflection, equips you with an "
        "authoritative spoken declaration, and provides sacred space to physically write down the burdens you release into God's hands."
    )
    story.append(Paragraph(intro_p2, intro_body))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>THE 4-STEP BEDTIME SANCTUARY RITUAL</b>", label_style))
    story.append(Spacer(1, 6))

    steps_data = [
        [
            Paragraph("<b>1. Disconnect & Be Still</b><br/><font color='#64748b'>Turn off bright screens, social feeds, and notifications 20 minutes before laying down. Settle into your quiet resting space.</font>", intro_body),
        ],
        [
            Paragraph("<b>2. Meditate on the Night's Scripture</b><br/><font color='#64748b'>Slowly read the focal scripture twice. Let the words wash over your mind, displacing fearful thoughts with divine truth.</font>", intro_body),
        ],
        [
            Paragraph("<b>3. Speak the Bedtime Declaration Aloud</b><br/><font color='#64748b'>Faith comes by hearing. Speak the sacred declaration with confidence, establishing God's protective atmosphere over your home.</font>", intro_body),
        ],
        [
            Paragraph("<b>4. Write & Release Your Cares</b><br/><font color='#64748b'>Physically write down the worries, people, and situations you are releasing into God's care tonight, followed by your daily mercies.</font>", intro_body),
        ],
    ]
    steps_table = Table(steps_data, colWidths=[540])
    steps_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(steps_table)
    story.append(Spacer(1, 14))

    benediction_box = [
        Paragraph(
            "<i>\"When thou liest down, thou shalt not be afraid: yea, thou shalt lie down, and thy sleep shall be sweet.\"</i><br/><b>— Proverbs 3:24 (KJV)</b>",
            scripture_style,
        )
    ]
    ben_table = Table([[benediction_box]], colWidths=[540])
    ben_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#2563eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(ben_table)
    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGES 3 TO 32: THE 30 NIGHTS
    # ---------------------------------------------------------
    for night in NIGHTS_DATA:
        # Header: Night X of 30 & Theme
        story.append(Paragraph(f"NIGHT {night.night_number} OF 30", theme_style))
        story.append(Paragraph(night.theme, title_style))
        story.append(Spacer(1, 4))

        # Scripture Plaque
        scrip_content = [
            Paragraph(f'"{night.scripture_text}"', scripture_style),
            Spacer(1, 2),
            Paragraph(f"— {night.scripture_ref}", scripture_ref_style),
        ]
        scrip_table = Table([[scrip_content]], colWidths=[540])
        scrip_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f7ff")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#2563eb")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(scrip_table)
        story.append(Spacer(1, 6))

        # Evening Meditation
        story.append(Paragraph("<b>EVENING MEDITATION</b>", label_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(night.meditation, meditation_style))
        story.append(Spacer(1, 6))

        # Spoken Bedtime Declaration
        story.append(Paragraph("<b>BEDTIME DECLARATION (SPEAK ALOUD)</b>", label_style))
        story.append(Spacer(1, 2))
        dec_content = [Paragraph(night.declaration, dec_style)]
        dec_table = Table([[dec_content]], colWidths=[540])
        dec_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fde68a")),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#f59e0b")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(dec_table)
        story.append(Spacer(1, 6))

        # Guided Evening Prayer
        story.append(Paragraph("<b>EVENING SURRENDER PRAYER</b>", label_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(f'"{night.prayer}"', prayer_style))
        story.append(Spacer(1, 6))

        # Bedside Ruled Journaling Section
        story.append(Paragraph("<b>BEDSIDE JOURNALING & SURRENDER</b>", label_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"<i>{night.prompt_surrender}</i>", prompt_style))
        story.append(Spacer(1, 1))

        # Ruled writing lines for surrender (3 lines, comfortable height)
        lines1 = Table([[""] for _ in range(3)], colWidths=[540], rowHeights=[17] * 3)
        lines1.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1"))]))
        story.append(lines1)
        story.append(Spacer(1, 5))

        # Ruled writing lines for gratitude (2 lines)
        story.append(Paragraph(f"<i>{night.prompt_gratitude}</i>", prompt_style))
        story.append(Spacer(1, 1))
        lines2 = Table([[""] for _ in range(2)], colWidths=[540], rowHeights=[17] * 2)
        lines2.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1"))]))
        story.append(lines2)

        story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 33: BEDSIDE EMERGENCY SCRIPTURE SHIELD
    # ---------------------------------------------------------
    emer_h1 = ParagraphStyle("EmerH1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#0f172a"))
    emer_sub = ParagraphStyle("EmerSub", fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor("#64748b"))
    emer_cat = ParagraphStyle("EmerCat", fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=colors.HexColor("#1e3a8a"))
    emer_text = ParagraphStyle("EmerText", fontName="Helvetica-Oblique", fontSize=8.5, leading=12, textColor=colors.HexColor("#334155"))
    emer_ref = ParagraphStyle("EmerRef", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#b45309"))

    story.append(Paragraph("Bedside Emergency Scripture Shield", emer_h1))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Instant promises to speak when awakened by sudden fear, insomnia, or grief in the middle of the night.", emer_sub))
    story.append(Spacer(1, 10))

    crisis_sections = [
        (
            "1. When Overcome by Sudden Panic or Heart Palpitations",
            [
                ("Psalm 56:3", "What time I am afraid, I will trust in thee."),
                ("2 Timothy 1:7", "For God hath not given us the spirit of fear; but of power, and of love, and of a sound mind."),
                ("Philippians 4:6-7", "Be careful for nothing; but in every thing by prayer... the peace of God shall keep your hearts."),
            ],
        ),
        (
            "2. When Battling Chronic Insomnia & Midnight Overthinking",
            [
                ("Psalm 127:2", "It is vain for you to rise up early, to sit up late, to eat the bread of sorrows: for so he giveth his beloved sleep."),
                ("Proverbs 3:24", "When thou liest down, thou shalt not be afraid: yea, thou shalt lie down, and thy sleep shall be sweet."),
                ("Psalm 4:8", "I will both lay me down in peace, and sleep: for thou, LORD, only makest me dwell in safety."),
            ],
        ),
        (
            "3. When Disturbed by Bad Dreams & Spiritual Oppression",
            [
                ("Psalm 91:5", "Thou shalt not be afraid for the terror by night; nor for the arrow that flieth by day."),
                ("Luke 10:19", "Behold, I give unto you power to tread on serpents and scorpions, and over all the power of the enemy."),
                ("Romans 8:31", "If God be for us, who can be against us?"),
            ],
        ),
        (
            "4. When Carrying Deep Grief, Loneliness, or Heartbreak",
            [
                ("Psalm 34:18", "The LORD is nigh unto them that are of a broken heart; and saveth such as be of a contrite spirit."),
                ("Matthew 28:20", "Lo, I am with you always, even unto the end of the world. Amen."),
                ("Psalm 147:3", "He healeth the broken in heart, and bindeth up their wounds."),
            ],
        ),
    ]

    for cat_title, verses in crisis_sections:
        story.append(Paragraph(cat_title, emer_cat))
        story.append(Spacer(1, 3))
        v_rows = []
        for ref, text in verses:
            v_rows.append([Paragraph(f"<b>{ref}</b>", emer_ref), Paragraph(f'"{text}"', emer_text)])

        vt = Table(v_rows, colWidths=[100, 440])
        vt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(vt)
        story.append(Spacer(1, 7))

    story.append(PageBreak())

    # ---------------------------------------------------------
    # PAGE 34: CLOSING BENEDICTION & MINISTRY PARTNER INVITATION
    # ---------------------------------------------------------
    close_h1 = ParagraphStyle("CloseH1", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"))
    close_h2 = ParagraphStyle("CloseH2", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=colors.HexColor("#2563eb"))
    close_body = ParagraphStyle("CloseBody", fontName="Helvetica", fontSize=9, leading=13.5, textColor=colors.HexColor("#334155"))

    story.append(Paragraph("May the Peace of God Rest Upon You", close_h1))
    story.append(Spacer(1, 3))
    story.append(Paragraph("THE PRIESTLY BENEDICTION (NUMBERS 6:24-26)", close_h2))
    story.append(Spacer(1, 10))

    priest_box = [
        Paragraph(
            "\"The LORD bless thee, and keep thee:<br/>"
            "The LORD make his face shine upon thee, and be gracious unto thee:<br/>"
            "The LORD lift up his countenance upon thee, and give thee peace.\"",
            ParagraphStyle("PriestText", fontName="Helvetica-Bold", fontSize=11, leading=16, textColor=colors.HexColor("#1e3a8a"), alignment=1),
        )
    ]
    p_table = Table([[priest_box]], colWidths=[540])
    p_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f7ff")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#93c5fd")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ]
        )
    )
    story.append(p_table)
    story.append(Spacer(1, 14))

    close_p = (
        "Thank you for journeying through these thirty nights with The Secret Place. "
        "Our prayer is that this companion has helped you establish a sacred bedtime altar, "
        "breaking the grip of insomnia and fear, and restoring your nights to deep, restorative peace in Christ. "
        "We broadcast daily scripture meditations, nightly prayers, and 432 Hz Solfeggio soundscapes to believers worldwide."
    )
    story.append(Paragraph(close_p, close_body))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>PARTNER WITH OUR GLOBAL OUTREACH</b>", label_style))
    story.append(Spacer(1, 6))

    partner_box = [
        Paragraph(
            "<b>• Sow a Voluntary Seed or Partner in Prayer:</b><br/>"
            f"<font color='#2563eb'>{SELAR_URL}</font><br/><br/>"
            "<b>• Subscribe to Nightly Video Prayers:</b><br/>"
            "YouTube: <font color='#2563eb'>https://www.youtube.com/@TheSecretPlace</font><br/><br/>"
            "<b>• Nightly Audio Podcast Stream:</b><br/>"
            "Available on Apple Podcasts & Spotify via our official RSS feed.<br/><br/>"
            "<i>The Secret Place is an independent editorial prayer sanctuary dedicated to streaming God's Word freely to the nations.</i>",
            close_body,
        )
    ]
    part_table = Table([[partner_box]], colWidths=[540])
    part_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    story.append(part_table)

    # Build Document with JournalNumberedCanvas
    doc.build(story, canvasmaker=JournalNumberedCanvas)
    return out_path
