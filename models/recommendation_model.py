# Heavy imports moved inside functions to speed up serverless cold starts

def recommend_groups(user, all_groups, top_k=5):
    """
    Recommend study groups to a user based on content-based filtering.
    """
    if not all_groups:
        return []

    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    # Prepare user profile text
    user_subjects = user.subjects if user.subjects else ""
    user_skill = user.skill_level if user.skill_level else ""
    user_availability = user.availability if user.availability else ""
    user_goals = user.learning_goals if user.learning_goals else ""
    
    user_text = f"{user_subjects} {user_skill} {user_availability} {user_goals}"
    
    # Prepare group profile texts
    group_texts = []
    group_ids = []
    
    for group in all_groups:
        group_subject = group.subject if group.subject else ""
        group_desc = group.description if group.description else ""
        group_time = group.meeting_time if group.meeting_time else ""
        
        group_text = f"{group_subject} {group_desc} {group_time}"
        group_texts.append(group_text)
        group_ids.append(group.id)

    # Combine all texts for consistent vectorization
    all_texts = [user_text] + group_texts
    
    # Check if empty
    if not any(all_texts):
        return all_groups[:top_k]
    
    # Feature extraction
    vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    except ValueError:
        return all_groups[:top_k] # For edge cases with only stop words
    
    # Calculate similarity
    user_vector = tfidf_matrix[0] # User is the first row
    group_vectors = tfidf_matrix[1:] # Groups are the rest
    
    cosine_sim = cosine_similarity(user_vector, group_vectors).flatten()
    
    # Rank groups based on similarity score
    ranked_indices = cosine_sim.argsort()[::-1]
    
    recommended_groups = []
    for idx in ranked_indices[:top_k]:
        # Don't recommend if the score is very weak
        if cosine_sim[idx] > 0.01:
            # Find the group object
            for group in all_groups:
                if group.id == group_ids[idx]:
                    recommended_groups.append(group)
                    break

    # Fallback to random/all if no strict matches but there are groups available
    if not recommended_groups and all_groups:
        return all_groups[:top_k]

    return recommended_groups


def recommend_partners(current_user, all_users, top_k=5):
    """
    Recommend study partners to a user based on profile similarity.
    Uses TF-IDF + Cosine Similarity on user profiles.
    """
    # Filter out the current user
    other_users = [u for u in all_users if u.id != current_user.id]
    if not other_users:
        return []

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    # Build profile text for the current user
    def build_profile_text(user):
        subjects = user.subjects if user.subjects else ""
        skill = user.skill_level if user.skill_level else ""
        availability = user.availability if user.availability else ""
        goals = user.learning_goals if user.learning_goals else ""
        return f"{subjects} {skill} {availability} {goals}"

    current_text = build_profile_text(current_user)
    other_texts = [build_profile_text(u) for u in other_users]

    all_texts = [current_text] + other_texts

    if not any(t.strip() for t in all_texts):
        return other_users[:top_k]

    vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    except ValueError:
        return other_users[:top_k]

    current_vector = tfidf_matrix[0]
    other_vectors = tfidf_matrix[1:]

    similarities = cosine_similarity(current_vector, other_vectors).flatten()

    ranked_indices = similarities.argsort()[::-1]

    partners = []
    for idx in ranked_indices[:top_k]:
        if similarities[idx] > 0.01:
            partners.append({
                'user': other_users[idx],
                'score': round(similarities[idx] * 100, 1)  # percentage match
            })

    return partners


def suggest_youtube_videos(group_subject, group_description="", num_suggestions=6):
    """
    Generate YouTube video search suggestions based on a group's subject and description.
    Returns a list of dicts with 'title' and 'url' for YouTube search links.
    """
    import urllib.parse

    subject = group_subject.strip() if group_subject else ""
    description = group_description.strip() if group_description else ""

    if not subject:
        return []

    # Generate diverse, helpful search queries from the group's subject
    search_queries = [
        f"{subject} tutorial for students",
        f"{subject} explained simply",
        f"{subject} crash course",
        f"{subject} lecture full course",
        f"{subject} tips and tricks",
        f"{subject} practice problems solved",
        f"{subject} real world examples",
        f"best {subject} resources for beginners",
    ]

    # If description has meaningful keywords, add a targeted query
    if description and len(description) > 10:
        # Extract first meaningful phrase from description (up to 50 chars)
        desc_snippet = description[:50].strip()
        search_queries.insert(0, f"{subject} {desc_snippet}")

    # Build YouTube search URLs
    suggestions = []
    display_titles = [
        f"📘 {subject} — Full Tutorial",
        f"💡 {subject} — Explained Simply",
        f"⚡ {subject} — Crash Course",
        f"🎓 {subject} — University Lecture",
        f"🔧 {subject} — Tips & Tricks",
        f"📝 {subject} — Practice Problems",
        f"🌍 {subject} — Real World Examples",
        f"🚀 Best {subject} Resources",
    ]

    # If description query was added, prepend a title for it
    if description and len(description) > 10:
        display_titles.insert(0, f"🎯 {subject} — Focused Topic")

    for i, query in enumerate(search_queries[:num_suggestions]):
        encoded_query = urllib.parse.quote_plus(query)
        suggestions.append({
            'title': display_titles[i] if i < len(display_titles) else f"📺 {subject} Video {i+1}",
            'query': query,
            'url': f"https://www.youtube.com/results?search_query={encoded_query}"
        })

    return suggestions
