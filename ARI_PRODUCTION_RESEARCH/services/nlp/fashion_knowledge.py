"""
Fashion Knowledge Base for LLM-RAG Intent Detection
Extracted from existing hardcoded vocabularies and styling rules
"""

FASHION_KNOWLEDGE_BASE = [
    # Category Knowledge
    {
        "type": "category_mapping",
        "content": "Tops include: shirt, blouse, top, tee, tank top, sweater, hoodie, t-shirt, camisole, tunic. These are upper body garments worn on the torso.",
        "keywords": ["tops", "shirt", "blouse", "top", "tee", "tank", "sweater", "hoodie", "t-shirt", "camisole", "tunic"],
        "category": "tops"
    },
    {
        "type": "category_mapping", 
        "content": "Bottoms include: pants, jeans, shorts, skirt, trousers, leggings. These are lower body garments worn on legs and hips.",
        "keywords": ["bottoms", "pants", "jeans", "shorts", "skirt", "trousers", "leggings"],
        "category": "bottoms"
    },
    {
        "type": "category_mapping",
        "content": "Dresses include: dress, gown, maxi dress, midi dress, mini dress, jumpsuit, romper. These are one-piece garments covering torso and legs.",
        "keywords": ["dresses", "dress", "gown", "maxi", "midi", "mini", "jumpsuit", "romper"],
        "category": "dresses"
    },
    {
        "type": "category_mapping",
        "content": "Outerwear includes: jacket, coat, blazer, cardigan, vest, trench coat, parka, bomber jacket. These are outer layer garments for warmth or style.",
        "keywords": ["outerwear", "jacket", "coat", "blazer", "cardigan", "vest", "trench", "parka", "bomber"],
        "category": "outerwear"
    },
    {
        "type": "category_mapping",
        "content": "Shoes include: shoes, boots, sneakers, heels, sandals, flats, athletic shoes. These are footwear worn on feet.",
        "keywords": ["shoes", "boots", "sneakers", "heels", "sandals", "flats"],
        "category": "shoes"
    },
    {
        "type": "category_mapping",
        "content": "Accessories include: bag, purse, wallet, belt, scarf, hat, jewelry, necklace, bracelet, earrings, ring, watch. These are supplementary items that complement outfits.",
        "keywords": ["accessories", "bag", "purse", "wallet", "belt", "scarf", "hat", "jewelry", "necklace", "bracelet", "earrings", "ring", "watch"],
        "category": "accessories"
    },
    {
        "type": "category_mapping",
        "content": "Activewear includes: athletic wear, gym clothes, workout clothes, yoga wear, sports clothing, running gear, athletic shoes, sportswear. These are garments designed for physical activity and exercise.",
        "keywords": ["activewear", "athletic", "gym", "workout", "yoga", "sports", "running", "sportswear"],
        "category": "activewear"
    },

    # Style Personality Knowledge
    {
        "type": "style_modifier",
        "content": "Casual style means: relaxed, comfortable, everyday, laid-back clothing. Think jeans, t-shirts, sneakers, and easy-to-wear pieces for informal occasions.",
        "keywords": ["casual", "relaxed", "comfortable", "everyday", "laid-back"],
        "style": "casual"
    },
    {
        "type": "style_modifier",
        "content": "Formal style means: business, professional, elegant, sophisticated clothing. Think suits, blazers, dress pants, dress shirts, and polished pieces for work or formal events.",
        "keywords": ["formal", "business", "professional", "elegant", "sophisticated"],
        "style": "formal"
    },
    {
        "type": "style_modifier",
        "content": "Trendy style means: fashionable, stylish, chic, modern clothing. Think current fashion trends, on-trend pieces, and contemporary styles.",
        "keywords": ["trendy", "fashionable", "stylish", "chic", "modern"],
        "style": "trendy"
    },
    {
        "type": "style_modifier",
        "content": "Vintage style means: retro, classic, timeless, antique clothing. Think pieces inspired by past decades, vintage cuts, and nostalgic fashion.",
        "keywords": ["vintage", "retro", "classic", "timeless", "antique"],
        "style": "vintage"
    },
    {
        "type": "style_modifier",
        "content": "Sporty style means: athletic, active, performance clothing. Think activewear, athleisure, sports-inspired pieces, and comfortable athletic clothing.",
        "keywords": ["sporty", "athletic", "active", "performance"],
        "style": "sporty"
    },
    {
        "type": "style_modifier",
        "content": "Bohemian style means: boho, hippie, free-spirited clothing. Think flowing fabrics, earthy tones, layered jewelry, and artistic, unconventional pieces.",
        "keywords": ["bohemian", "boho", "hippie", "free-spirited"],
        "style": "bohemian"
    },
    {
        "type": "style_modifier",
        "content": "Minimalist style means: simple, clean, basic, understated clothing. Think neutral colors, simple lines, quality basics, and uncluttered looks.",
        "keywords": ["minimalist", "minimal", "simple", "clean", "basic", "understated"],
        "style": "minimalist"
    },
    {
        "type": "style_modifier",
        "content": "Edgy style means: punk, rock, alternative, bold clothing. Think leather, dark colors, statement pieces, and unconventional fashion choices.",
        "keywords": ["edgy", "punk", "rock", "alternative", "bold"],
        "style": "edgy"
    },

    # Occasion-Based Styling Intelligence
    {
        "type": "occasion_styling",
        "content": "Wedding attire: For wedding guests, choose elegant dresses, sophisticated suits, dress shoes, refined accessories, jewelry, clutches. Ensure appropriate coverage, flowing fabrics, and timeless pieces that photograph beautifully. Avoid white, ivory, or anything too attention-grabbing.",
        "keywords": ["wedding", "wedding guest", "ceremony", "reception"],
        "occasion": "wedding"
    },
    {
        "type": "occasion_styling", 
        "content": "Interview attire: For job interviews, choose professional blazers, crisp dress shirts, tailored pants or skirts, polished dress shoes, minimal jewelry, structured professional bags. Focus on authoritative presence pieces that convey competence and professionalism.",
        "keywords": ["interview", "job interview", "professional meeting", "work interview"],
        "occasion": "interview"
    },
    {
        "type": "occasion_styling",
        "content": "Casual outings: For casual events, choose comfortable jeans, versatile t-shirts, casual sneakers, relaxed dresses, cozy sweaters, easy-care fabrics. Focus on approachable styling and comfort for everyday activities.",
        "keywords": ["casual", "casual outing", "everyday", "weekend", "relaxed"],
        "occasion": "casual"
    },
    {
        "type": "occasion_styling",
        "content": "Date night attire: For romantic dates, choose flattering tops, well-fitted pants or skirts, stylish heels or dress shoes, confidence-building statement accessories, romantic touches. Focus on pieces that make you feel attractive and confident.",
        "keywords": ["date", "date night", "romantic", "dinner date", "dating"],
        "occasion": "date"
    },
    {
        "type": "occasion_styling",
        "content": "Work/business attire: For office work, choose structured blazers, professional dress pants, quality button-downs, appropriate work shoes, credible accessories. Focus on polished appearance pieces that convey professionalism and competence.",
        "keywords": ["work", "business", "office", "professional", "corporate"],
        "occasion": "work"
    },
    {
        "type": "occasion_styling",
        "content": "Party attire: For parties and celebrations, choose fun party dresses, trendy tops, statement jewelry, celebratory pieces, conversation-starting items. Focus on bold but tasteful choices that reflect the festive mood.",
        "keywords": ["party", "celebration", "birthday party", "cocktail party", "social event"],
        "occasion": "party"
    },
    {
        "type": "occasion_styling",
        "content": "Travel attire: For travel, prioritize comfortable yet stylish pieces, versatile layers, wrinkle-resistant fabrics, coordinating items. Focus on practical but fashionable choices that work in multiple settings.",
        "keywords": ["travel", "vacation", "trip", "traveling", "journey"],
        "occasion": "travel"
    },
    {
        "type": "occasion_styling",
        "content": "Gym/workout attire: For exercise, choose athletic wear, moisture-wicking fabrics, supportive sports bras, comfortable athletic shoes, performance leggings. Focus on functional pieces that allow for movement and breathability.",
        "keywords": ["gym", "workout", "exercise", "fitness", "athletic", "sports"],
        "occasion": "gym"
    },

    # Color Knowledge
    {
        "type": "color_knowledge",
        "content": "Color variations and synonyms: Navy means dark blue, burgundy means dark red/wine color, olive means dark green, coral means orange-pink, sage means grayish green, charcoal means dark gray, ivory means off-white/cream, khaki means tan/beige, rose means pink, wine means deep red, forest means dark green, emerald means bright green, crimson means bright red, indigo means dark purple-blue.",
        "keywords": ["navy", "burgundy", "olive", "coral", "sage", "charcoal", "ivory", "khaki", "rose", "wine", "forest", "emerald", "crimson", "indigo"],
    },

    # Material Knowledge
    {
        "type": "material_knowledge",
        "content": "Fabric characteristics: Cotton is breathable and comfortable for everyday wear. Silk is luxurious and elegant for formal occasions. Wool is warm and suitable for cold weather. Linen is lightweight and perfect for summer. Cashmere is soft and luxurious for premium pieces. Denim is durable and casual. Leather is stylish and durable for accessories and outerwear. Chiffon is light and flowing for feminine pieces.",
        "keywords": ["cotton", "silk", "wool", "linen", "cashmere", "denim", "leather", "chiffon", "satin", "velvet"],
    },

    # Brand Knowledge
    {
        "type": "brand_knowledge", 
        "content": "Luxury brands include: Chanel, Dior, Gucci, Prada, Versace, Balenciaga, Saint Laurent, Bottega Veneta, Burberry, Givenchy, Valentino, Fendi, Celine, Loewe, Hermes, Louis Vuitton, Tom Ford, Alexander McQueen, Stella McCartney, Miu Miu. These are high-end designer brands known for quality and prestige.",
        "keywords": ["chanel", "dior", "gucci", "prada", "versace", "balenciaga", "saint laurent", "bottega veneta", "burberry", "givenchy", "valentino", "fendi", "celine", "loewe", "hermes", "louis vuitton", "tom ford", "alexander mcqueen", "stella mccartney", "miu miu", "luxury", "designer"],
    },

    # Intent Pattern Knowledge
    {
        "type": "intent_patterns",
        "content": "Browse intent indicators: When users say 'show me', 'browse', 'what do you have', 'explore', 'see what', or 'looking around', they want to explore options without specific requirements.",
        "keywords": ["show me", "browse", "what do you have", "explore", "see what", "looking around"],
        "intent": "browse"
    },
    {
        "type": "intent_patterns",
        "content": "Specific item intent indicators: When users say 'looking for', 'need', 'want', 'find me', 'search for', or 'where can i find', they have a specific item or type of item in mind.",
        "keywords": ["looking for", "need", "want", "find me", "search for", "where can i find"],
        "intent": "specific_item"
    },
    {
        "type": "intent_patterns",
        "content": "Inspiration intent indicators: When users say 'inspire me', 'inspiration', 'ideas for', 'suggest', 'what should i wear', 'help me choose', or 'not sure what', they want styling suggestions and inspiration.",
        "keywords": ["inspire me", "inspiration", "ideas for", "suggest", "what should i wear", "help me choose", "not sure what"],
        "intent": "inspiration"
    },
    {
        "type": "intent_patterns",
        "content": "Gift intent indicators: When users mention 'gift', 'present', 'for my', 'for someone', 'birthday', 'anniversary', or 'special occasion', they're shopping for someone else.",
        "keywords": ["gift", "present", "for my", "for someone", "birthday", "anniversary", "special occasion"],
        "intent": "gift"
    },
    {
        "type": "intent_patterns",
        "content": "Outfit intent indicators: When users mention 'outfit', 'complete look', 'goes with', 'match with', 'coordinate', 'style with', or 'wear together', they want multiple coordinated pieces.",
        "keywords": ["outfit", "complete look", "goes with", "match with", "coordinate", "style with", "wear together"],
        "intent": "outfit"
    },

    # Size Knowledge
    {
        "type": "size_knowledge",
        "content": "Size conversions and variations: XS means extra small (size 0-2), S means small (size 4-6), M means medium (size 8-10), L means large (size 12-14), XL means extra large (size 16-18). Petite refers to shorter proportions, Plus refers to larger sizes (18+), Tall refers to longer proportions.",
        "keywords": ["xs", "s", "m", "l", "xl", "xxl", "petite", "plus", "tall", "extra small", "small", "medium", "large", "extra large"],
    },

    # Semantic Understanding
    {
        "type": "semantic_understanding",
        "content": "Synonym relationships: 'Flowy' means loose, flowing, airy, or draped fabric. 'Comfy' means comfortable, cozy, or relaxed. 'Cute' means attractive, pretty, or charming. 'Dressy' means formal, elegant, or sophisticated. 'Trendy' means fashionable, stylish, or current. 'Classic' means timeless, traditional, or enduring style.",
        "keywords": ["flowy", "comfy", "cute", "dressy", "trendy", "classic", "loose", "flowing", "comfortable", "cozy", "attractive", "formal", "fashionable", "timeless"],
    }
]

def get_fashion_knowledge_for_embedding():
    """Get all fashion knowledge as text for embedding"""
    return [entry["content"] for entry in FASHION_KNOWLEDGE_BASE]

def get_relevant_knowledge(query_keywords):
    """Get relevant knowledge entries based on query keywords"""
    relevant = []
    query_lower = [k.lower() for k in query_keywords]
    
    for entry in FASHION_KNOWLEDGE_BASE:
        entry_keywords = entry.get("keywords", [])
        if any(keyword.lower() in query_lower for keyword in entry_keywords):
            relevant.append(entry)
    
    return relevant