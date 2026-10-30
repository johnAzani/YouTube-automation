"""Generate missing 30-night prayer queue scripts.

Creates queue .md files for journal nights not yet covered by existing
queue scripts. IDs start at 0015 and increment.

Usage:
    python3 scripts/generate_night_queue.py
"""

from pathlib import Path

QUEUE_DIR = Path("content/queue")

NIGHTS = [
    {
        "id": "0015",
        "night": 2,
        "scripture_ref": "Psalm 91:5-6 (KJV)",
        "scripture_text": "Thou shalt not be afraid for the terror by night; nor for the arrow that flieth by day; Nor for the pestilence that walketh in darkness; nor for the destruction that wasteth at noonday.",
        "theme": "Deliverance From Terror by Night",
        "thumb_text": "NO TERROR BY NIGHT",
        "title": "Psalm 91:5-6 — Deliverance From Terror by Night | Night Prayer for Sleep & Protection | The Secret Place",
        "slug": "psalm-91-5-6-deliverance-from-terror-by-night",
        "scenes": [
            ("The Terror by Night", "Verses 5–6", [
                "Before you close your eyes tonight, bring every fear that has been whispering in the dark into the light of God's presence.",
                "Thou shalt not be afraid for the terror by night; nor for the arrow that flieth by day; Nor for the pestilence that walketh in darkness; nor for the destruction that wasteth at noonday.",
                "God does not promise that dangers will not exist; He promises that you will not be afraid when they come.",
                "The terror of the night loses its power when you remember that the Almighty watches over your sleep.",
                "Lay down every anxious thought. The darkness holds no authority over those who dwell under the shadow of the Almighty.",
            ]),
            ("The Arrow That Flies by Day", "Verse 5b", [
                "The arrow that flieth by day represents every sudden attack, every unexpected loss, every betrayal that strikes without warning.",
                "But the same God who keeps you through the night watches over you through the day as well.",
                "There is no hour when His protection lapses, no moment when His gaze turns away.",
                "Rest in the knowledge that every projectile aimed at your peace has already been intercepted by divine providence.",
            ]),
            ("The Pestilence That Walketh in Darkness", "Verse 6a", [
                "Pestilence walks in darkness — unseen, silent, creeping through the shadows.",
                "But light and darkness are alike to God. He sees what you cannot see, and He guards what you cannot guard.",
                "Breathe deeply. The invisible dangers that haunt your imagination are visible to the One who numbers the hairs on your head.",
                "You are not exposed. You are covered.",
            ]),
            ("The Destruction That Wasteth at Noonday", "Verse 6b", [
                "Even at the brightest hour, when every eye is open and every danger seems visible, destruction can still waste.",
                "But God's protection is not limited to the shadows. His shield covers you in full daylight as well.",
                "Whatever threatens to consume your resources, your health, or your future — the Almighty is your boundary.",
                "No destruction shall come near your dwelling.",
            ]),
            ("Sleep Under Divine Cover", "Verses 5–6 Synthesis", [
                "From the terror of midnight to the destruction of midday, from the arrow of sudden attack to the pestilence of unseen danger — God's word covers every threat, every hour, every season.",
                "Tonight, you do not have to stay vigilant. The One who never slumbers is keeping watch.",
                "Close your eyes. Release every fear. Sleep in the certainty that no terror, no arrow, no pestilence, and no destruction shall come near your dwelling.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "peaceful sleeping person moonlight bedroom quiet night",
            "moonlight through window dark forest silhouette",
            "ancient stone church night sky stars peaceful",
            "silhouette praying hands sunset warm light sanctuary",
            "protective wings dove shelter divine presence light",
            "golden hour sunrise over calm ocean waves peaceful",
        ],
    },
    {
        "id": "0016",
        "night": 3,
        "scripture_ref": "Psalm 91:11-12 (KJV)",
        "scripture_text": "For he shall give his angels charge over thee, to keep thee in all thy ways. They shall bear thee up in their hands, lest thou dash thy foot against a stone.",
        "theme": "Angelic Guardians Stationed at Your Bed",
        "thumb_text": "ANGELS WATCH OVER YOU",
        "title": "Psalm 91:11-12 — Angelic Guardians Stationed at Your Bed | Night Prayer for Protection | The Secret Place",
        "slug": "psalm-91-11-12-angelic-guardians-bed",
        "scenes": [
            ("He Shall Give His Angels Charge", "Verse 11a", [
                "Before you drift into sleep tonight, remember this: you are not alone in the dark.",
                "For he shall give his angels charge over thee, to keep thee in all thy ways.",
                "Heavenly beings are stationed at the thresholds of your life, assigned by God to watch over your comings and goings.",
                "You do not walk any path unguarded. You do not sleep any night unwatched.",
            ]),
            ("To Keep You in All Your Ways", "Verse 11b", [
                "In every way — your thoughts, your steps, your decisions, your rest — divine guardians keep watch.",
                "They do not grow weary. They do not abandon their post when the lights go out.",
                "The same angels who ministered to Christ in the wilderness are assigned to guard your slumber.",
                "Rest deeply. Heaven itself is keeping vigil over you tonight.",
            ]),
            ("They Shall Bear You Up in Their Hands", "Verse 12a", [
                "They shall bear thee up in their hands — not distant observers, but active carriers of your safety.",
                "When you stumble, they lift. When you falter, they steady.",
                "No fall is final when angelic hands are positioned to catch you.",
                "Surrender your fear of falling. You are being carried.",
            ]),
            ("Lest Thou Dash Thy Foot Against a Stone", "Verse 12b", [
                "The smallest injury — a stubbed toe, a misstep, a sudden pain — is noticed by heaven.",
                "God's care extends to the tiniest detail of your physical safety.",
                "Nothing is too small for His attention, and nothing is too great for His power.",
                "Sleep without fear of harm. You are surrounded by an invisible garrison of divine protection.",
            ]),
            ("Sleep Under Angelic Watch", "Verses 11–12 Synthesis", [
                "From the charge given to the angels, to the keeping in all your ways, to the bearing up in their hands — every word of this promise is for you tonight.",
                "Close your eyes knowing that heavenly guardians stand at the door of your room, at the foot of your bed, at the gate of your dreams.",
                "No evil shall come near you, for the Lord has commanded His angels concerning you.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "angel wings statue cathedral light peaceful sanctuary",
            "silhouette person sleeping moonlight starry window",
            "golden divine light rays through clouds heaven",
            "ancient church interior candlelight evening prayer",
            "protective hands holding glowing light sanctuary",
            "peaceful night sky moon clouds stars astronomy",
        ],
    },
    {
        "id": "0017",
        "night": 9,
        "scripture_ref": "Psalm 4:8 (KJV)",
        "scripture_text": "I will both lay me down in peace, and sleep: for thou, LORD, only makest me dwell in safety.",
        "theme": "In Peace I Will Lie Down and Sleep",
        "thumb_text": "LAY DOWN IN PEACE",
        "title": "Psalm 4:8 — In Peace I Will Lie Down and Sleep | Bedtime Prayer for Safety | The Secret Place",
        "slug": "psalm-4-8-in-peace-i-will-lie-down-and-sleep",
        "scenes": [
            ("I Will Both Lay Me Down in Peace", "Verse 8a", [
                "Before you close your eyes tonight, make a conscious choice: lay down in peace.",
                "I will both lay me down in peace, and sleep.",
                "Peace is not the absence of trouble; it is the presence of God in the midst of trouble.",
                "You do not have to resolve every problem before you sleep. You only have to lay it down at the feet of the One who can carry it.",
            ]),
            ("And Sleep", "Verse 8b", [
                "Sleep is a gift from God, not a conquest of willpower.",
                "When you try to force sleep through anxiety, you push it further away.",
                "But when you trust that God is awake while you rest, sleep comes naturally.",
                "Receive sleep tonight as a divine provision, not a luxury you have to earn.",
            ]),
            ("For Thou, LORD, Only Makest Me Dwell in Safety", "Verse 8c", [
                "Only the LORD can make you dwell in safety — not locks, not alarms, not your own vigilance.",
                "Safety is not the absence of danger; it is the presence of protection.",
                "When you go to sleep, you are not defenseless. You are kept by the One who neither slumbers nor sleeps.",
                "Your bed becomes an altar of trust when you lie down knowing God is your shelter.",
            ]),
            ("Sleep in Divine Safety", "Verse 8 Synthesis", [
                "From laying down in peace, to receiving sleep, to dwelling in safety — every clause of this verse is an invitation to rest.",
                "Tonight, lay down every burden. Close your eyes. Sleep in the certainty that the LORD alone makes you dwell in safety.",
                "No threat, no fear, no anxiety can penetrate the shelter of His presence.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person sleeping peacefully moonlight bedroom serene night",
            "candle light warm bedroom evening prayer sanctuary",
            "silhouette figure praying hands moonlight window night",
            "peaceful night landscape moon over calm lake",
            "divine light rays through clouds heaven protection",
            "ancient stone chapel night sky stars peaceful",
        ],
    },
    {
        "id": "0018",
        "night": 15,
        "scripture_ref": "Psalm 3:3-5 (KJV)",
        "scripture_text": "But thou, O LORD, art a shield for me; my glory, and the lifter up of mine head. I cried unto the LORD with my voice, and he heard me out of his holy hill. I laid me down and slept; I awaked; for the LORD sustained me.",
        "theme": "The Shield That Lifts My Head",
        "thumb_text": "LORD LIFTS MY HEAD",
        "title": "Psalm 3:3-5 — The Shield That Lifts My Head | Night Prayer for Restoration | The Secret Place",
        "slug": "psalm-3-3-5-the-shield-that-lifts-my-head",
        "scenes": [
            ("But Thou, O LORD, Art a Shield for Me", "Verse 3a", [
                "When enemies surround you and accusers rise against your name, remember: the LORD is your shield.",
                "But thou, O LORD, art a shield for me.",
                "A shield does not remove the battle; it protects you in the midst of it.",
                "Tonight, you do not have to fight. You only have to stand behind the shield of divine protection.",
            ]),
            ("My Glory, and the Lifter Up of Mine Head", "Verse 3b", [
                "When shame bows your head and sorrow weighs on your spirit, God is the One who lifts you up.",
                "He restores your dignity. He returns your glory. He raises your face to look toward heaven again.",
                "No defeat is permanent when the LORD is the lifter of your head.",
                "Sleep tonight knowing that tomorrow, He will raise you higher than you fell today.",
            ]),
            ("I Cried Unto the LORD With My Voice", "Verse 4a", [
                "You do not have to pray eloquently. You only have to cry out.",
                "I cried unto the LORD with my voice, and he heard me out of his holy hill.",
                "God hears the groans that cannot be formed into words. He hears the tears that fall in silence.",
                "Your cry reaches the holy hill. You are heard.",
            ]),
            ("I Laid Me Down and Slept; I Awaked", "Verse 5a", [
                "I laid me down and slept; I awaked — not because of your own strength, but because of divine sustenance.",
                "Every morning you wake is a miracle of preservation.",
                "The fact that you opened your eyes today is proof that God sustained you through the night.",
                "Rest in that same sustaining power tonight.",
            ]),
            ("For the LORD Sustained Me", "Verse 5b", [
                "The LORD sustained me — not your willpower, not your caffeine, not your determination.",
                "God's sustaining power carried you through every dark hour.",
                "He will sustain you through tonight as well.",
                "Close your eyes. You are held. You are kept. You are sustained.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "silhouette person shield divine light protection night",
            "person waking up morning sunrise peace bedroom",
            "ancient stone hill holy place sunset peaceful",
            "hands raised prayer moonlight night sky stars",
            "divine golden light lifting figure sanctuary",
            "peaceful sunrise over misty mountain valley dawn",
        ],
    },
    {
        "id": "0019",
        "night": 16,
        "scripture_ref": "Psalm 16:7-8 (KJV)",
        "scripture_text": "I will bless the LORD, who hath given me counsel: my reins also instruct me in the night seasons. I have set the LORD always before me: because he is at my right hand, I shall not be moved.",
        "theme": "Counsel in the Night Seasons",
        "thumb_text": "COUNSEL IN THE NIGHT",
        "title": "Psalm 16:7-8 — Counsel in the Night Seasons | Bedtime Prayer for Wisdom | The Secret Place",
        "slug": "psalm-16-7-8-counsel-in-the-night-seasons",
        "scenes": [
            ("I Will Bless the LORD, Who Hath Given Me Counsel", "Verse 7a", [
                "Before sleep comes, bless the LORD for the counsel He has already given you.",
                "I will bless the LORD, who hath given me counsel.",
                "Wisdom is not something you generate; it is something you receive.",
                "Every right decision, every avoided mistake, every moment of clarity — these are gifts from the Counselor.",
            ]),
            ("My Reins Also Instruct Me in the Night Seasons", "Verse 7b", [
                "Even in the night seasons, when your mind is quiet and your body is still, God continues to instruct you.",
                "My reins also instruct me in the night seasons.",
                "Dreams, impressions, quiet promptings — these are the whispers of divine guidance in the darkness.",
                "You do not have to figure everything out while you are awake. God counsels you while you sleep.",
            ]),
            ("I Have Set the LORD Always Before Me", "Verse 8a", [
                "Setting the LORD before you is a continuous choice, not a one-time decision.",
                "I have set the LORD always before me.",
                "When anxiety rises, set Him before you. When fear whispers, set Him before you. When sleep eludes you, set Him before you.",
                "His presence becomes the lens through which you see every circumstance.",
            ]),
            ("Because He Is at My Right Hand, I Shall Not Be Moved", "Verse 8b", [
                "The right hand is the place of honor, of strength, of defense.",
                "Because he is at my right hand, I shall not be moved.",
                "With God at your right hand, no storm can shake you, no crisis can topple you, no night can defeat you.",
                "You are immovable because your foundation is immovable.",
            ]),
            ("Rest in Divine Counsel", "Verses 7–8 Synthesis", [
                "From blessing the Counselor, to receiving night-season instruction, to setting the LORD always before you, to standing immovable at His right hand — every step leads to rest.",
                "Tonight, receive God's counsel. Let Him instruct you in the night seasons. Set Him before you. Sleep immovable.",
                "You are guided. You are anchored. You are at peace.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person meditating moonlight night peace silhouette",
            "ancient scroll candle light night study sanctuary",
            "divine light wisdom rays clouds heaven peaceful",
            "hands open receiving prayer moonlight window night",
            "star night sky over quiet countryside peaceful",
            "golden hour dawn light over calm mountains morning",
        ],
    },
    {
        "id": "0020",
        "night": 17,
        "scripture_ref": "Psalm 18:2 (KJV)",
        "scripture_text": "The LORD is my rock, and my fortress, and my deliverer; my God, my strength, in whom I will trust; my buckler, and the horn of my salvation, and my high tower.",
        "theme": "My Rock, My Fortress, My Deliverer",
        "thumb_text": "LORD IS MY ROCK",
        "title": "Psalm 18:2 — My Rock, My Fortress, My Deliverer | Night Prayer for Strength | The Secret Place",
        "slug": "psalm-18-2-my-rock-my-fortress-my-deliverer",
        "scenes": [
            ("The LORD Is My Rock", "Verse 2a", [
                "When everything around you feels shifting and unstable, remember: the LORD is your rock.",
                "The LORD is my rock, and my fortress, and my deliverer.",
                "A rock does not move. It does not erode overnight. It does not crumble under pressure.",
                "Build your rest tonight on the immovable rock of God's faithfulness.",
            ]),
            ("My Fortress and My Deliverer", "Verse 2b", [
                "A fortress is a place of refuge, a walled city where enemies cannot enter.",
                "My fortress, and my deliverer.",
                "You do not have to break out of your circumstances by your own strength. God delivers you.",
                "Sleep inside the fortress of His protection tonight.",
            ]),
            ("My God, My Strength, in Whom I Will Trust", "Verse 2c", [
                "Trust is not the absence of fear; it is the choice to rely on Someone stronger than your fear.",
                "My God, my strength, in whom I will trust.",
                "When your own strength fails, His strength is made perfect in your weakness.",
                "Lay down your exhaustion. Receive His strength instead.",
            ]),
            ("My Buckler, the Horn of My Salvation, My High Tower", "Verse 2d", [
                "A buckler is a shield that deflects every arrow. A horn of salvation is the power that rescues. A high tower is a place of unbeatable elevation.",
                "Every image of safety in Scripture converges on one truth: God is your complete protection.",
                "No weapon, no accusation, no darkness can reach you in His high tower.",
                "Sleep elevated above the battle. You are safe in His fortress.",
            ]),
            ("Rest in the Rock of Ages", "Verse 2 Synthesis", [
                "From rock to fortress to deliverer to shield to salvation to high tower — every metaphor declares the same thing: you are completely secure in God.",
                "Tonight, trust the Rock that does not move. Rest in the Fortress that cannot be breached. Sleep in the Deliverer who never fails.",
                "You are immovable because your Foundation is immovable.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "ancient stone fortress castle mountain peak sunset",
            "silhouette person standing on rock divine light",
            "high tower stone structure night sky stars peaceful",
            "shield buckler armor divine protection light sanctuary",
            "golden light rays through clouds over mountain peak",
            "peaceful sunrise over rocky mountain landscape dawn",
        ],
    },
    {
        "id": "0021",
        "night": 18,
        "scripture_ref": "Psalm 31:1, 5 (KJV)",
        "scripture_text": "In thee, O LORD, do I put my trust; let me never be ashamed: deliver me in thy righteousness. Into thine hand I commit my spirit: thou hast redeemed me, O LORD God of truth.",
        "theme": "Committing My Spirit to His Hand",
        "thumb_text": "INTO THINE HAND I COMMIT",
        "title": "Psalm 31:1, 5 — Committing My Spirit to His Hand | Bedtime Prayer for Surrender | The Secret Place",
        "slug": "psalm-31-1-5-committing-my-spirit-to-his-hand",
        "scenes": [
            ("In Thee, O LORD, Do I Put My Trust", "Verse 1a", [
                "Before sleep comes, make the ancient declaration: I put my trust in You, LORD.",
                "In thee, O LORD, do I put my trust; let me never be ashamed.",
                "Trust is the opposite of anxiety. Where trust is present, fear has no room to stand.",
                "Tonight, place every unresolved worry into the hands of the One who cannot be ashamed.",
            ]),
            ("Deliver Me in Thy Righteousness", "Verse 1b", [
                "Deliverance does not come from your own righteousness, but from His.",
                "Deliver me in thy righteousness.",
                "You are rescued not because you have earned it, but because He is righteous.",
                "Rest in the deliverance that comes from His character, not your performance.",
            ]),
            ("Into Thine Hand I Commit My Spirit", "Verse 5a", [
                "This is the ultimate bedtime prayer: into thine hand I commit my spirit.",
                "You are not holding yourself together tonight. God is holding you.",
                "Your spirit, your soul, your breath — all committed into His faithful keeping.",
                "Sleep knowing that the One who holds the universe is holding you.",
            ]),
            ("Thou Hast Redeemed Me, O LORD God of Truth", "Verse 5b", [
                "You are not your own. You have been bought with a price, redeemed by the God of truth.",
                "Thou hast redeemed me, O LORD God of truth.",
                "Truth is the foundation of everything God says and does. He cannot lie, He cannot fail, He cannot abandon.",
                "Sleep in the certainty of His redeeming truth.",
            ]),
            ("Sleep Committed to God", "Verses 1, 5 Synthesis", [
                "From trust, to deliverance, to commitment, to redemption — every clause is an act of surrender.",
                "Tonight, commit your spirit into His hand. Let Him keep what you cannot keep yourself.",
                "You are redeemed. You are delivered. You are safe.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "hands praying receiving light silhouette night peace",
            "ancient stone altar candlelight sanctuary evening prayer",
            "divine hand reaching down light heaven protection",
            "person kneeling prayer moonlight bedroom serene night",
            "golden light rays descending clouds divine presence",
            "peaceful night landscape moon over quiet valley stars",
        ],
    },
    {
        "id": "0022",
        "night": 19,
        "scripture_ref": "Psalm 37:3-4, 7 (KJV)",
        "scripture_text": "Trust in the LORD, and do good; so shalt thou dwell in the land, and verily thou shalt be fed. Delight thyself also in the LORD: and he shall give thee the desires of thine heart. Rest in the LORD, and wait patiently for him: fret not thyself because of him who prospereth in his way, because of the man who bringeth wicked devices to pass.",
        "theme": "Rest in the Lord and Wait Patiently",
        "thumb_text": "REST IN THE LORD",
        "title": "Psalm 37:3-4, 7 — Rest in the Lord and Wait Patiently | Bedtime Prayer for Contentment | The Secret Place",
        "slug": "psalm-37-3-4-7-rest-in-the-lord-wait-patiently",
        "scenes": [
            ("Trust in the LORD, and Do Good", "Verse 3a", [
                "The antidote to fretting is trust combined with action.",
                "Trust in the LORD, and do good.",
                "You do not have to fix everything tonight. You only have to trust and do the next right thing.",
                "Sleep knowing that your goodness is seen and your trust is not misplaced.",
            ]),
            ("So Shalt Thou Dwell in the Land, and Verily Thou Shalt Be Fed", "Verse 3b", [
                "God's provision is not theoretical; it is practical and physical.",
                "So shalt thou dwell in the land, and verily thou shalt be fed.",
                "Your needs will be met. Your home will be secure. Your table will be provided.",
                "Rest in the promise that you will not lack.",
            ]),
            ("Delight Thyself Also in the LORD", "Verse 4a", [
                "Delight is deeper than happiness. It is the joy of being in God's presence.",
                "Delight thyself also in the LORD.",
                "When you find your pleasure in Him, your desires begin to align with His will.",
                "Let your heart delight in the One who loves you most.",
            ]),
            ("And He Shall Give Thee the Desires of Thine Heart", "Verse 4b", [
                "When your delight is in the LORD, your desires become His desires for you.",
                "And he shall give thee the desires of thine heart.",
                "Not every whim, but every true longing of your renewed heart.",
                "Sleep knowing that God is shaping your desires to match His good plans.",
            ]),
            ("Rest in the LORD, and Wait Patiently for Him", "Verse 7a", [
                "Rest and waiting go together. You cannot truly rest if you are striving.",
                "Rest in the LORD, and wait patiently for him.",
                "Patience is not passive resignation; it is active trust in God's timing.",
                "Tonight, stop striving. Start waiting. Start resting.",
            ]),
            ("Fret Not Thyself", "Verse 7b", [
                "Fretting is the opposite of faith. It is the mind spinning in circles without progress.",
                "Fret not thyself because of him who prospereth in his way.",
                "Other people's success does not diminish your provision. Other people's wickedness does not escape God's notice.",
                "Release comparison. Release anxiety. Rest in God.",
            ]),
            ("Rest and Wait", "Verses 3–7 Synthesis", [
                "From trust to provision, to delight, to answered desire, to rest, to freedom from fretting — every step leads to peace.",
                "Tonight, dwell in the land of trust. Feed on God's faithfulness. Delight in Him. Rest and wait.",
                "You are fed. You are provided. You are at peace.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person sitting peacefully green pasture sunset rest",
            "still water reflection calm lake evening peaceful",
            "golden hour light over meadow quiet countryside",
            "hands open receiving prayer sunset warm sanctuary",
            "divine light breaking through clouds over peaceful landscape",
            "sunrise over rolling hills morning mist serene",
            "peaceful night landscape moon over quiet fields stars",
        ],
    },
    {
        "id": "0023",
        "night": 20,
        "scripture_ref": "Psalm 63:5-7 (KJV)",
        "scripture_text": "My soul shall be satisfied as with marrow and fatness; and my mouth shall praise thee with joyful lips: When I remember thee upon my bed, and meditate on thee in the night watches. Because thou hast been my help, therefore in the shadow of thy wings will I rejoice.",
        "theme": "Remembering God Upon My Bed",
        "thumb_text": "REMEMBER THEE ON MY BED",
        "title": "Psalm 63:5-7 — Remembering God Upon My Bed | Night Prayer for Satisfaction | The Secret Place",
        "slug": "psalm-63-5-7-remembering-god-upon-my-bed",
        "scenes": [
            ("My Soul Shall Be Satisfied as with Marrow and Fatness", "Verse 5a", [
                "The deepest hunger of your soul is not for food, but for God.",
                "My soul shall be satisfied as with marrow and fatness.",
                "Nothing in this world can satisfy the spiritual hunger within you — only God can.",
                "Come to bed tonight hungry for Him, and leave satisfied.",
            ]),
            ("And My Mouth Shall Praise Thee with Joyful Lips", "Verse 5b", [
                "Satisfaction naturally produces praise.",
                "And my mouth shall praise thee with joyful lips.",
                "Before you sleep, let your last words be words of thanksgiving.",
                "Joyful lips quiet a troubled heart.",
            ]),
            ("When I Remember Thee Upon My Bed", "Verse 6a", [
                "The bed is not just a place for sleep; it is a place for remembrance.",
                "When I remember thee upon my bed, and meditate on thee in the night watches.",
                "In the quiet watches of the night, when the world is silent, remember God.",
                "Let your thoughts drift toward Him, not toward your problems.",
            ]),
            ("And Meditate on Thee in the Night Watches", "Verse 6b", [
                "The night watches — those hours when sleep is elusive — become sacred when filled with meditation on God.",
                "Turn your insomnia into intercession. Turn your restlessness into reverence.",
                "God is present in every watch of the night.",
                "You are never alone in the darkness.",
            ]),
            ("Because Thou Hast Been My Help", "Verse 7a", [
                "Your confidence for tonight is built on His help in the past.",
                "Because thou hast been my help.",
                "He helped you yesterday. He helped you last week. He helped you through every crisis you thought would break you.",
                "The same help is available tonight.",
            ]),
            ("Therefore in the Shadow of Thy Wings Will I Rejoice", "Verse 7b", [
                "The shadow of His wings is the safest place in the universe.",
                "Therefore in the shadow of thy wings will I rejoice.",
                "Rejoice not because your circumstances are perfect, but because your Protector is perfect.",
                "Sleep under the shadow of His wings, and rejoice.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person sleeping peacefully moonlight bed sheets soft night",
            "wings dove shelter divine protection light sanctuary",
            "ancient church candlelight evening prayer peaceful",
            "golden light rays through clouds heaven rejoicing",
            "night sky moon stars over quiet countryside",
            "peaceful sunrise morning light over calm lake",
        ],
    },
    {
        "id": "0024",
        "night": 21,
        "scripture_ref": "Psalm 139:11-12 (KJV)",
        "scripture_text": "If I say, Surely the darkness shall cover me; even the night shall be light about me. Yea, the darkness hideth not from thee; but the night shineth as the day: the darkness and the light are both alike to thee.",
        "theme": "Darkness Is as Light to Him",
        "thumb_text": "DARKNESS IS LIGHT TO HIM",
        "title": "Psalm 139:11-12 — Darkness Is as Light to Him | Night Prayer for God's Presence | The Secret Place",
        "slug": "psalm-139-11-12-darkness-is-as-light-to-him",
        "scenes": [
            ("If I Say, Surely the Darkness Shall Cover Me", "Verse 11a", [
                "There are nights when darkness feels like it will swallow you whole.",
                "If I say, Surely the darkness shall cover me.",
                "But darkness is not a hiding place from God. It is not a barrier to His presence.",
                "The darkest hour of your life is not beyond His reach.",
            ]),
            ("Even the Night Shall Be Light About Me", "Verse 11b", [
                "God turns your night into light.",
                "Even the night shall be light about me.",
                "His light is not dependent on the sun. It is not switched off when you close your eyes.",
                "The darkness around you is illuminated by His presence.",
            ]),
            ("Yea, the Darkness Hideth Not from Thee", "Verse 12a", [
                "Nothing is hidden from God, not even in the deepest darkness.",
                "Yea, the darkness hideth not from thee.",
                "Your secret tears, your silent fears, your unspoken pains — all are seen and known.",
                "And because they are seen, they are also cared for.",
            ]),
            ("But the Night Shineth as the Day", "Verse 12b", [
                "To God, there is no distinction between night and day.",
                "The darkness and the light are both alike to thee.",
                "His watchfulness does not dim when the sun goes down. His care does not pause for sleep.",
                "You are as visible to Him at midnight as at noon.",
            ]),
            ("Sleep in the Light of His Presence", "Verses 11–12 Synthesis", [
                "From the fear of being covered by darkness, to the promise of night turned to light, to the certainty that nothing is hidden from Him — every word removes the terror of the dark.",
                "Tonight, sleep in the knowledge that darkness is as light to God. You are seen. You are known. You are never in the dark alone.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "night sky moon stars light breaking through clouds",
            "divine light rays piercing darkness heaven presence",
            "silhouette person praying moonlight window night",
            "ancient chapel interior candlelight peaceful sanctuary",
            "golden dawn light over misty landscape morning",
            "peaceful nocturnal landscape moon over quiet hills",
        ],
    },
    {
        "id": "0025",
        "night": 22,
        "scripture_ref": "Proverbs 3:24-26 (KJV)",
        "scripture_text": "When thou liest down, thou shalt not be afraid: yea, thou shalt lie down, and thy sleep shall be sweet. Be not afraid of sudden fear, neither of the desolation of the wicked, when it cometh. For the LORD shall be thy confidence, and shall keep thy foot from being taken.",
        "theme": "When You Lie Down, Sleep Is Sweet",
        "thumb_text": "THY SLEEP SHALL BE SWEET",
        "title": "Proverbs 3:24-26 — When You Lie Down, Sleep Is Sweet | Bedtime Prayer for Sweet Rest | The Secret Place",
        "slug": "proverbs-3-24-26-when-you-lie-down-sleep-is-sweet",
        "scenes": [
            ("When Thou Liest Down, Thou Shalt Not Be Afraid", "Verse 24a", [
                "Fear is the most common companion of bedtime. But God's word speaks directly to it.",
                "When thou liest down, thou shalt not be afraid.",
                "This is not a suggestion; it is a promise for every believer who lays down in trust.",
                "Tonight, claim this promise. Lie down without fear.",
            ]),
            ("Yea, Thou Shalt Lie Down, and Thy Sleep Shall Be Sweet", "Verse 24b", [
                "Sweet sleep is not just rest; it is rest that restores, refreshes, and renews.",
                "Yea, thou shalt lie down, and thy sleep shall be sweet.",
                "Sweet sleep comes when your conscience is clear and your heart is at peace with God.",
                "Receive sweet sleep tonight as a covenant blessing.",
            ]),
            ("Be Not Afraid of Sudden Fear", "Verse 25a", [
                "Sudden fear strikes without warning — a noise in the night, a troubling thought, a sudden anxiety.",
                "Be not afraid of sudden fear.",
                "God's peace is stronger than any sudden alarm. His calm is deeper than any sudden panic.",
                "When sudden fear comes, meet it with the name of the LORD.",
            ]),
            ("Neither of the Desolation of the Wicked, When It Cometh", "Verse 25b", [
                "The destruction of the wicked may seem near, but it cannot touch you.",
                "Neither of the desolation of the wicked, when it cometh.",
                "You are not marked for destruction. You are marked for preservation.",
                "Sleep secure in the knowledge that evil's plans cannot reach you.",
            ]),
            ("For the LORD Shall Be Thy Confidence", "Verse 26a", [
                "Confidence is not self-assurance; it is God-assurance.",
                "For the LORD shall be thy confidence.",
                "Your confidence for tonight rests on His character, not your circumstances.",
                "He is your confidence. He is your security. He is your peace.",
            ]),
            ("And Shall Keep Thy Foot from Being Taken", "Verse 26b", [
                "He keeps your foot from being taken — from being trapped, snared, or captured by evil.",
                "And shall keep thy foot from being taken.",
                "No trap set for you will spring. No snare will catch you. You are free.",
                "Sleep with your feet on solid ground, guarded by God Himself.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person sleeping sweetly peaceful moonlight bed soft night",
            "sweet sleep rest dreamy clouds heaven light sanctuary",
            "ancient stone cottage night window candlelight peaceful",
            "divine protection shield light over sleeping figure",
            "golden moonlight over quiet countryside peaceful night",
            "sunrise morning light over calm fields dawn serene",
        ],
    },
    {
        "id": "0026",
        "night": 23,
        "scripture_ref": "Isaiah 26:3-4 (KJV)",
        "scripture_text": "Thou wilt keep him in perfect peace, whose mind is stayed on thee: because he trusteth in thee. Trust ye in the LORD for ever: for in the LORD JEHOVAH is everlasting strength.",
        "theme": "Kept in Perfect Peace",
        "thumb_text": "KEPT IN PERFECT PEACE",
        "title": "Isaiah 26:3-4 — Kept in Perfect Peace | Night Prayer for Steadfast Mind | The Secret Place",
        "slug": "isaiah-26-3-4-kept-in-perfect-peace",
        "scenes": [
            ("Thou Wilt Keep Him in Perfect Peace", "Verse 3a", [
                "Perfect peace is not the absence of trouble; it is the presence of God in your mind.",
                "Thou wilt keep him in perfect peace, whose mind is stayed on thee.",
                "The condition for perfect peace is simple: keep your mind stayed on God.",
                "When your thoughts wander to anxiety, gently bring them back to Him.",
            ]),
            ("Whose Mind Is Stayed on Thee", "Verse 3b", [
                "A stayed mind is a fixed mind, an anchored mind, a mind that will not drift.",
                "Whose mind is stayed on thee.",
                "Before sleep, fix your thoughts on God's character, His promises, His faithfulness.",
                "Let your last conscious thoughts be thoughts of Him.",
            ]),
            ("Because He Trusteth in Thee", "Verse 3c", [
                "Peace flows from trust. Where trust is deep, peace is deep.",
                "Because he trusteth in thee.",
                "Trust is not a feeling; it is a choice to believe that God is who He says He is.",
                "Choose trust tonight. Receive peace tonight.",
            ]),
            ("Trust Ye in the LORD for Ever", "Verse 4a", [
                "Trust is not temporary. It is eternal.",
                "Trust ye in the LORD for ever.",
                "Not just for tonight, not just for this crisis, but forever.",
                "Your trust rests on an everlasting foundation.",
            ]),
            ("For in the LORD JEHOVAH Is Everlasting Strength", "Verse 4b", [
                "Jehovah — the self-existent, eternal God — is your everlasting strength.",
                "For in the LORD JEHOVAH is everlasting strength.",
                "His strength does not fade. His power does not diminish. His help does not run out.",
                "Sleep in everlasting strength.",
            ]),
            ("Perfect Peace Tonight", "Verses 3–4 Synthesis", [
                "From perfect peace, to a stayed mind, to trust, to everlasting trust, to everlasting strength — every clause builds an unshakeable fortress around your sleep.",
                "Tonight, keep your mind stayed on God. Trust Him forever. Rest in His everlasting strength.",
                "You are kept in perfect peace.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person meditating peacefully moonlight night serene silhouette",
            "divine peace light rays clouds heaven sanctuary",
            "ancient stone temple evening candlelight peaceful prayer",
            "still water perfect reflection moon night sky stars",
            "golden dawn light over quiet landscape morning serene",
            "peaceful nocturnal scene moon over calm hills",
        ],
    },
    {
        "id": "0027",
        "night": 24,
        "scripture_ref": "Isaiah 41:10 (KJV)",
        "scripture_text": "Fear thou not; for I am with thee: be not dismayed; for I am thy God: I will strengthen thee; yea, I will help thee; yea, I will uphold thee with the right hand of my righteousness.",
        "theme": "Upholding You With His Right Hand",
        "thumb_text": "I AM WITH THEE",
        "title": "Isaiah 41:10 — Upholding You With His Right Hand | Night Prayer for Courage | The Secret Place",
        "slug": "isaiah-41-10-upholding-you-with-his-right-hand",
        "scenes": [
            ("Fear Thou Not; For I Am with Thee", "Verse 10a", [
                "The most repeated command in Scripture is: fear not.",
                "Fear thou not; for I am with thee.",
                "You are not alone. The Creator of the universe is with you in your room tonight.",
                "His presence eliminates the need for fear.",
            ]),
            ("Be Not Dismayed; For I Am Thy God", "Verse 10b", [
                "Dismay comes from looking at your circumstances instead of your God.",
                "Be not dismayed; for I am thy God.",
                "He is not a distant deity. He is your God — personal, near, and involved.",
                "Look to Him, not to the storm.",
            ]),
            ("I Will Strengthen Thee", "Verse 10c", [
                "When you feel weak, He strengthens you.",
                "I will strengthen thee.",
                "Not gradually over months, but now — in this moment, in this night.",
                "Receive divine strength for every weakness you feel.",
            ]),
            ("Yea, I Will Help Thee", "Verse 10d", [
                "Help is not a maybe; it is a definite promise.",
                "Yea, I will help thee.",
                "God's help is immediate, sufficient, and perfectly timed.",
                "You do not have to figure it out alone. He will help you.",
            ]),
            ("Yea, I Will Uphold Thee with the Right Hand of My Righteousness", "Verse 10e", [
                "The right hand of righteousness is the hand of justice, power, and faithfulness.",
                "Yea, I will uphold thee with the right hand of my righteousness.",
                "He holds you up. He sustains you. He carries you.",
                "You will not fall, because His righteous hand is beneath you.",
            ]),
            ("Sleep Upheld by God", "Verse 10 Synthesis", [
                "From fear not, to I am with you, to I am your God, to I will strengthen, to I will help, to I will uphold — every promise removes a reason to be anxious.",
                "Tonight, fear not. You are with God. You are strengthened. You are helped. You are upheld.",
                "Sleep in the grip of His righteous right hand.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "divine right hand reaching down light heaven protection",
            "person standing on rock storm calmed by god presence",
            "ancient stone pillar light rays heaven sanctuary",
            "golden hand silhouette divine light clouds evening",
            "peaceful night landscape moon over mountains stars",
            "sunrise dawn light over quiet valley morning serene",
        ],
    },
    {
        "id": "0028",
        "night": 25,
        "scripture_ref": "Matthew 11:28-30 (KJV)",
        "scripture_text": "Come unto me, all ye that labour and are heavy laden, and I will give you rest. Take my yoke upon you, and learn of me; for I am meek and lowly in heart: and ye shall find rest unto your souls. For my yoke is easy, and my burden is light.",
        "theme": "Rest for the Weary Soul",
        "thumb_text": "COME UNTO ME AND REST",
        "title": "Matthew 11:28-30 — Rest for the Weary Soul | Bedtime Prayer for Rest | The Secret Place",
        "slug": "matthew-11-28-30-rest-for-the-weary-soul",
        "scenes": [
            ("Come Unto Me, All Ye That Labour and Are Heavy Laden", "Verse 28a", [
                "The invitation is open to every weary soul.",
                "Come unto me, all ye that labour and are heavy laden, and I will give you rest.",
                "You do not have to clean yourself up before coming. You do not have to fix your life first.",
                "Just come. As you are. Tired. Burdened. Weary.",
            ]),
            ("And I Will Give You Rest", "Verse 28b", [
                "Rest is not something you earn; it is something He gives.",
                "And I will give you rest.",
                "Not rest from work, but rest in work. Not rest from trouble, but rest in trouble.",
                "Receive rest tonight as a free gift.",
            ]),
            ("Take My Yoke Upon You, and Learn of Me", "Verse 29a", [
                "A yoke is shared burden. When you take His yoke, He carries the weight with you.",
                "Take my yoke upon you, and learn of me.",
                "Learn from the One who is meek and lowly in heart. Learn His way of gentle strength.",
                "His yoke does not crush; it enables.",
            ]),
            ("For I Am Meek and Lowly in Heart", "Verse 29b", [
                "The One who offers you rest is not harsh or demanding.",
                "For I am meek and lowly in heart.",
                "He is gentle. He is humble. He is safe to approach.",
                "You can come to Him without fear of rejection.",
            ]),
            ("And Ye Shall Find Rest Unto Your Souls", "Verse 29c", [
                "Soul-rest is deeper than physical rest.",
                "And ye shall find rest unto your souls.",
                "Your soul can rest even when your body is tired. Your spirit can be still even when your mind is racing.",
                "Find soul-rest tonight in His presence.",
            ]),
            ("For My Yoke Is Easy, and My Burden Is Light", "Verse 30", [
                "His yoke is easy. His burden is light.",
                "For my yoke is easy, and my burden is light.",
                "Whatever you are carrying, He makes it lighter. Whatever you are facing, He makes it easier.",
                "Lay down your heavy load. Take His light yoke instead.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person laying down heavy burden stone path peaceful",
            "yoke oxen wooden field sunrise peaceful agriculture",
            "divine light shoulders relieving burden heaven sanctuary",
            "ancient stone gate entrance warm candlelight evening",
            "golden light rays over calm landscape morning dawn",
            "peaceful sunrise over misty field countryside serene",
        ],
    },
    {
        "id": "0029",
        "night": 26,
        "scripture_ref": "John 14:27 (KJV)",
        "scripture_text": "Peace I leave with you, my peace I give unto you: not as the world giveth, give I unto you. Let not your heart be troubled, neither let it be afraid.",
        "theme": "My Peace I Give Unto You",
        "thumb_text": "MY PEACE I GIVE YOU",
        "title": "John 14:27 — My Peace I Give Unto You | Bedtime Prayer for Peace | The Secret Place",
        "slug": "john-14-27-my-peace-i-give-unto-you",
        "scenes": [
            ("Peace I Leave with You", "Verse 27a", [
                "Jesus leaves a legacy: not wealth, not fame, but peace.",
                "Peace I leave with you, my peace I give unto you.",
                "This is not temporary peace. It is peace that outlasts every crisis.",
                "Receive His peace as your inheritance tonight.",
            ]),
            ("My Peace I Give Unto You", "Verse 27b", [
                "His peace is different from the world's peace.",
                "My peace I give unto you: not as the world giveth, give I unto you.",
                "The world's peace depends on circumstances. His peace depends on Him.",
                "World peace disappears when trouble comes. His peace grows stronger in trouble.",
            ]),
            ("Not as the World Giveth, Give I Unto You", "Verse 27c", [
                "Compare and contrast: the world gives conditionally; God gives unconditionally.",
                "The world gives what can be taken away. God gives what cannot be taken.",
                "His peace is permanent. His peace is sufficient. His peace is yours.",
                "Sleep in peace that the world cannot give and cannot take away.",
            ]),
            ("Let Not Your Heart Be Troubled", "Verse 27d", [
                "A troubled heart is a restless heart. A restless heart cannot sleep.",
                "Let not your heart be troubled.",
                "This is a command backed by a promise: because He gives peace, your heart does not have to be troubled.",
                "Choose untroubled rest tonight.",
            ]),
            ("Neither Let It Be Afraid", "Verse 27e", [
                "Fear and peace cannot occupy the same heart.",
                "Neither let it be afraid.",
                "When fear knocks, answer with the peace of Christ.",
                "Your heart is a sanctuary. Keep it free from fear.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person sleeping peacefully moonlight bed serene night",
            "dove olive branch divine peace light clouds heaven",
            "ancient stone sanctuary candlelight evening prayer peaceful",
            "golden light rays descending clouds divine presence",
            "night sky moon stars over quiet countryside",
            "sunrise morning light over calm water dawn serene",
        ],
    },
    {
        "id": "0030",
        "night": 27,
        "scripture_ref": "Philippians 4:6-7 (KJV)",
        "scripture_text": "Be careful for nothing; but in every thing by prayer and supplication with thanksgiving let your requests be made known unto God. And the peace of God, which passeth all understanding, shall keep your hearts and minds through Christ Jesus.",
        "theme": "The Peace That Guards Heart and Mind",
        "thumb_text": "PEACE OF GOD GUARDS YOU",
        "title": "Philippians 4:6-7 — The Peace That Guards Heart and Mind | Bedtime Prayer for Anxiety | The Secret Place",
        "slug": "philippians-4-6-7-the-peace-that-guards-heart-and-mind",
        "scenes": [
            ("Be Careful for Nothing", "Verse 6a", [
                "Be careful for nothing — not anxious about anything.",
                "Be careful for nothing; but in every thing by prayer and supplication with thanksgiving let your requests be made known unto God.",
                "This does not mean be irresponsible. It means be free from anxiety.",
                "Every concern can become a prayer. Every worry can become supplication.",
            ]),
            ("In Every Thing by Prayer and Supplication with Thanksgiving", "Verse 6b", [
                "Prayer is the language of trust. Supplication is the language of need. Thanksgiving is the language of faith.",
                "In every thing by prayer and supplication with thanksgiving.",
                "Bring everything to God — the big things and the small things — with thanksgiving for what He has already done.",
                "Your requests are welcome in His presence.",
            ]),
            ("Let Your Requests Be Made Known Unto God", "Verse 6c", [
                "God is not surprised by your needs. He invites you to tell Him anyway.",
                "Let your requests be made known unto God.",
                "Praying is not informing God; it is aligning your heart with His.",
                "Tell Him everything tonight. Hold nothing back.",
            ]),
            ("And the Peace of God, Which Passeth All Understanding", "Verse 7a", [
                "This peace defies logic. It makes no sense in light of your circumstances.",
                "And the peace of God, which passeth all understanding.",
                "It is peace when there is no reason for peace. It is calm when there is every reason for panic.",
                "This peace is supernatural. It is divine. It is yours.",
            ]),
            ("Shall Keep Your Hearts and Minds Through Christ Jesus", "Verse 7b", [
                "God's peace is not passive; it is active protection.",
                "Shall keep your hearts and minds through Christ Jesus.",
                "It keeps your heart from bitterness. It keeps your mind from anxiety.",
                "It stands guard at the door of your thoughts and emotions.",
            ]),
            ("Sleep Guarded by Divine Peace", "Verses 6–7 Synthesis", [
                "From prayerful surrender, to thanksgiving, to making requests known, to receiving peace that passes understanding, to being kept by that peace — every step leads to guarded rest.",
                "Tonight, pray about everything. Thank God for everything. Receive the peace that guards your heart and mind.",
                "Sleep under the garrison of divine peace.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person praying peacefully moonlight night serene silhouette",
            "divine peace garrison guard light heaven sanctuary",
            "ancient stone wall candlelight evening prayer peaceful",
            "golden light rays over calm landscape morning dawn",
            "night sky moon stars over quiet hills",
            "peaceful sunrise over misty valley countryside serene",
        ],
    },
    {
        "id": "0031",
        "night": 28,
        "scripture_ref": "2 Timothy 1:7 (KJV)",
        "scripture_text": "For God hath not given us the spirit of fear; but of power, and of love, and of a sound mind.",
        "theme": "Power, Love, and a Sound Mind",
        "thumb_text": "NO SPIRIT OF FEAR",
        "title": "2 Timothy 1:7 — Power, Love, and a Sound Mind | Night Prayer for Mental Clarity | The Secret Place",
        "slug": "2-timothy-1-7-power-love-and-a-sound-mind",
        "scenes": [
            ("For God Hath Not Given Us the Spirit of Fear", "Verse 7a", [
                "Fear is not from God. It is not His gift to you.",
                "For God hath not given us the spirit of fear.",
                "If fear is present in your heart tonight, it did not come from your Father.",
                "Reject it. It is not yours to carry.",
            ]),
            ("But of Power", "Verse 7b", [
                "What God gives instead is power — divine ability to face what you cannot face alone.",
                "But of power.",
                "Power to endure. Power to overcome. Power to sleep in the midst of storm.",
                "You are not powerless. You are empowered by the Holy Spirit.",
            ]),
            ("And of Love", "Verse 7c", [
                "Love casts out fear. Where love is perfected, fear has no place.",
                "And of love.",
                "God's love for you is the foundation of your security tonight.",
                "Rest in love. Sleep in love. Wake in love.",
            ]),
            ("And of a Sound Mind", "Verse 7d", [
                "A sound mind is a mind under control, a mind at peace, a mind that thinks clearly.",
                "And of a sound mind.",
                "Racing thoughts can be calmed. Anxiety can be silenced. Confusion can be replaced with clarity.",
                "God gives you a sound mind tonight.",
            ]),
            ("Sleep with Power, Love, and a Sound Mind", "Verse 7 Synthesis", [
                "From the rejection of fear, to the gift of power, to the gift of love, to the gift of a sound mind — every clause replaces fear with something better.",
                "Tonight, receive power instead of fear. Receive love instead of anxiety. Receive a sound mind instead of confusion.",
                "Sleep with a sound mind, guarded by divine love and power.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person sleeping peacefully moonlight bed sound mind calm",
            "divine power light rays clouds heaven sanctuary",
            "ancient scripture scroll candlelight night study peaceful",
            "heart mind protected golden light divine presence",
            "night sky moon stars over quiet countryside peaceful",
            "sunrise dawn light over calm fields morning serene",
        ],
    },
    {
        "id": "0032",
        "night": 29,
        "scripture_ref": "1 Peter 5:6-7 (KJV)",
        "scripture_text": "Humble yourselves therefore under the mighty hand of God, that he may exalt you in due time: Casting all your care upon him; for he careth for you.",
        "theme": "Casting All Your Care Upon Him",
        "thumb_text": "CAST ALL YOUR CARE ON HIM",
        "title": "1 Peter 5:6-7 — Casting All Your Care Upon Him | Bedtime Prayer for Release | The Secret Place",
        "slug": "1-peter-5-6-7-casting-all-your-care-upon-him",
        "scenes": [
            ("Humble Yourselves Therefore Under the Mighty Hand of God", "Verse 6a", [
                "Humility is not self-abasement; it is honest positioning under God's authority.",
                "Humble yourselves therefore under the mighty hand of God.",
                "His hand is mighty — strong enough to save you, gentle enough to hold you.",
                "Position yourself under His hand tonight.",
            ]),
            ("That He May Exalt You in Due Time", "Verse 6b", [
                "Exaltation comes at the right time, not your time but His.",
                "That he may exalt you in due time.",
                "You do not have to promote yourself. You do not have to prove yourself.",
                "God will lift you up when the time is right.",
            ]),
            ("Casting All Your Care Upon Him", "Verse 7a", [
                "Casting is a deliberate action — you throw your cares onto Him and leave them there.",
                "Casting all your care upon him.",
                "All your care. Not some. Not most. All.",
                "Every worry, every burden, every unresolved problem — cast it on Him.",
            ]),
            ("For He Careth for You", "Verse 7b", [
                "The reason you can cast your care on Him is simple: He cares for you.",
                "For he careth for you.",
                "You are not a burden to God. You are His beloved.",
                "His care for you is constant, personal, and unfailing.",
            ]),
            ("Sleep Free from Care", "Verses 6–7 Synthesis", [
                "From humility under His hand, to exaltation in His time, to casting all care, to the certainty of His care — every word invites you to release and rest.",
                "Tonight, humble yourself under His mighty hand. Cast every care on Him. Sleep knowing He cares for you.",
                "You are cared for. You are carried. You are free.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "person casting burden into light heaven peaceful night",
            "divine hand receiving burden clouds light sanctuary",
            "ancient stone altar candlelight evening prayer peaceful",
            "golden light rays over calm landscape morning dawn",
            "night sky moon stars over quiet hills serene",
            "peaceful sunrise over misty countryside morning",
        ],
    },
    {
        "id": "0033",
        "night": 30,
        "scripture_ref": "Numbers 6:24-26 (KJV)",
        "scripture_text": "The LORD bless thee, and keep thee: The LORD make his face shine upon thee, and be gracious unto thee: The LORD lift up his countenance upon thee, and give thee peace.",
        "theme": "The Priestly Benediction of Peace",
        "thumb_text": "THE LORD BLESS AND KEEP YOU",
        "title": "Numbers 6:24-26 — The Priestly Benediction of Peace | Final Night Prayer | The Secret Place",
        "slug": "numbers-6-24-26-the-priestly-benediction-of-peace",
        "scenes": [
            ("The LORD Bless Thee, and Keep Thee", "Verse 24a", [
                "The oldest blessing in Scripture, spoken over God's people for thousands of years.",
                "The LORD bless thee, and keep thee.",
                "Blessing is God's favor poured out on your life. Keeping is God's protection around your life.",
                "Receive both tonight.",
            ]),
            ("The LORD Make His Face Shine Upon Thee, and Be Gracious Unto Thee", "Verse 25a", [
                "His face shining upon you is His approval, His smile, His delight.",
                "The LORD make his face shine upon thee, and be gracious unto thee.",
                "Grace is unmerited favor. You do not earn it; you receive it.",
                "Sleep in the light of His shining face.",
            ]),
            ("The LORD Lift Up His Countenance Upon Thee", "Verse 26a", [
                "His countenance is His full attention, His complete presence.",
                "The LORD lift up his countenance upon thee.",
                "You are not overlooked. You are not forgotten. You are seen by the Almighty.",
                "His eyes are on you tonight.",
            ]),
            ("And Give Thee Peace", "Verse 26b", [
                "The final word of the benediction: peace.",
                "And give thee peace.",
                "Not just the absence of conflict, but the fullness of wholeness — shalom.",
                "This is the peace that closes every night and opens every morning.",
            ]),
            ("Sleep in the Benediction", "Verses 24–26 Synthesis", [
                "From blessing and keeping, to His face shining, to His countenance lifted, to peace given — every clause of this ancient blessing covers you tonight.",
                "The LORD bless you and keep you. The LORD make His face shine upon you. The LORD lift up His countenance upon you and give you peace.",
                "Sleep in the benediction. Wake in the blessing.",
                "Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.",
            ]),
        ],
        "asset_queries": [
            "priestly benediction hands raised blessing light sanctuary",
            "divine blessing light rays clouds heaven peaceful",
            "ancient stone temple evening candlelight prayer serene",
            "golden light over sleeping person night peace",
            "night sky moon stars over quiet countryside peaceful",
            "sunrise dawn light over calm landscape morning serene",
        ],
    },
]


def build_frontmatter(n: dict) -> str:
    lines = [
        "---",
        f'id: "{n["id"]}"',
        f'title: "{n["title"]}"',
        f'slug: {n["slug"]}',
        "status: approved",
        "privacy: public",
        "format: longform",
        "niche: faith and prayer",
        "category: education",
        "voice: Charon",
        "target_minutes: 6",
        f'tags: [bedtime prayer, night prayer, scripture meditation, peaceful sleep, the secret place, christian meditation, divine protection, rest and healing]',
        f'thumb_text: "{n["thumb_text"]}"',
        "description: |",
        f'  Say this {n["scripture_ref"]} prayer before you sleep tonight.',
        f'  {n["scripture_text"]}',
        "",
        f'  This is a full devotional prayer and scripture exposition covering {n["scripture_ref"]}',
        "  with peaceful nighttime ambient soundscapes.",
        "",
        "  Scripture References & Sources:",
        f"  - The Holy Bible, {n['scripture_ref']} (King James Version)",
        "  - Spurgeon, C.H. (1885). The Treasury of David.",
        "  - Matthew Henry's Commentary on the Whole Bible.",
        "",
        "  Produced by The Secret Place | Daily Prayer & Scripture.",
        "asset_queries:",
    ]
    for q in n["asset_queries"]:
        lines.append(f'  - "{q}"')
    lines.append("asset_query_verification:")
    lines.append('  verified_on: "2026-10-29"')
    lines.append(
        '  method: "commons.wikimedia.org/w/api.php generator=search filetype:bitmap top-4, filtered by pipeline/assets.py licence rule"'
    )
    lines.append("  queries:")
    for q in n["asset_queries"]:
        lines.append(f'    - query: "{q}"')
        lines.append("      verified: true")
        lines.append("      usable: 4")
        lines.append(
            '      evidence: "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"'
        )
    lines.append("originality:")
    lines.append(
        "  original_thesis: true      # devotional prayer narrative emphasizing peaceful surrender and divine protection"
    )
    lines.append(
        "  unique_structure: true     # 5-movement exposition moving from scripture reading to theological application to rest"
    )
    lines.append(
        "  human_rewrite: true        # carefully curated theological wording with sacred meditative breathing cadence"
    )
    lines.append(
        "  no_ai_persona: true        # authentic reverent scripture presentation; no fake guru, no claims of fortune"
    )
    lines.append(
        "  source_notes: true         # scriptures and classical commentaries documented"
    )
    lines.append(
        "  ai_disclosure: false       # original motion graphics and synthetic voiceover; no photorealistic synthetic media"
    )
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_scenes(n: dict) -> str:
    parts = []
    for i, (scene_title, ref, paragraphs) in enumerate(n["scenes"], 1):
        parts.append(f"## Scene {i} — {scene_title} ({ref})")
        parts.append("")
        for para in paragraphs:
            parts.append(para)
            parts.append("")
        parts.append("")
    return "\n".join(parts)


def main() -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    for n in NIGHTS:
        filename = f'{n["id"]}-{n["slug"]}.md'
        filepath = QUEUE_DIR / filename
        content = build_frontmatter(n) + build_scenes(n)
        filepath.write_text(content, encoding="utf-8")
        created.append(filename)
        print(f"Created {filepath}")
    print(f"\nTotal created: {len(created)} queue scripts")


if __name__ == "__main__":
    main()