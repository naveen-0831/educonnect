def recommend_groups(user, all_groups, top_k=5):
    """
    Lite version of group recommendations using simple keyword matching.
    No longer requires Pandas or Scikit-Learn.
    """
    if not all_groups:
        return []

    user_interests = set((user.subjects or "").lower().replace(',', ' ').split())
    
    scored_groups = []
    for group in all_groups:
        group_text = f"{group.name} {group.subject} {group.description}".lower()
        # Count how many user interest words appear in the group text
        score = sum(1 for word in user_interests if word in group_text)
        
        # Bonus for exact subject match
        if user.subjects and group.subject and group.subject.lower() in user.subjects.lower():
            score += 2
            
        scored_groups.append((score, group))

    # Sort by score descending
    scored_groups.sort(key=lambda x: x[0], reverse=True)
    
    return [g[1] for g in scored_groups[:top_k] if g[0] > 0] or all_groups[:top_k]


def recommend_partners(current_user, all_users, top_k=5):
    """
    Lite version of partner recommendations using interest overlap.
    """
    user_interests = set((current_user.subjects or "").lower().replace(',', ' ').split())
    
    scored_partners = []
    for other_user in all_users:
        if other_user.id == current_user.id:
            continue
            
        other_interests = set((other_user.subjects or "").lower().replace(',', ' ').split())
        # Calculate Jaccard-like similarity
        overlap = len(user_interests.intersection(other_interests))
        
        if overlap > 0 or (current_user.skill_level == other_user.skill_level):
            score = (overlap * 20) + (10 if current_user.skill_level == other_user.skill_level else 0)
            scored_partners.append({
                'user': other_user,
                'score': min(score, 99) # Cap at 99%
            })

    scored_partners.sort(key=lambda x: x['score'], reverse=True)
    return scored_partners[:top_k]


def suggest_youtube_videos(group_subject, group_description="", num_suggestions=6):
    import urllib.parse
    subject = group_subject.strip() if group_subject else "Education"
    
    queries = [
        f"{subject} tutorial",
        f"{subject} for beginners",
        f"{subject} crash course",
        f"advanced {subject} concepts"
    ]
    
    suggestions = []
    for i, q in enumerate(queries[:num_suggestions]):
        suggestions.append({
            'title': f"📺 {q.title()}",
            'query': q,
            'url': f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}"
        })
    return suggestions
